"""Pipeline orchestrator for the Adjudication Engine."""

from decimal import Decimal
from typing import Any, Dict, List

from src.models.claims import LineItem
from src.services.adjudication_engine.context_builder import add_line_item_to_context
from src.services.rule_engine.engine import evaluate_rule
from src.shared.enums import ExecutionPhase, LineItemStatus


def _determine_line_item_status(billed: Decimal, insurer_payable: Decimal, was_excluded: bool) -> LineItemStatus:
    """Determine the line item status based on financial outcome."""
    if was_excluded:
        return LineItemStatus.EXCLUDED
    if insurer_payable <= Decimal("0.00"):
        return LineItemStatus.DENIED
    if insurer_payable < billed:
        return LineItemStatus.PARTIALLY_APPROVED
    return LineItemStatus.APPROVED


def run_pipeline(
    base_context: Dict[str, Any],
    line_items: List[LineItem],
    rules: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Run the adjudication pipeline sequentially across all line items and phases.
    
    Args:
        base_context: The flattened context object built by ContextBuilder.
        line_items: List of LineItem SQLAlchemy model instances.
        rules: List of active rules for the policy's plan, fetched from DB.
        
    Returns:
        A list of dictionaries containing updated financials and audit trails 
        for each line item, ready for persistence.
    """
    # Group rules by phase
    rules_by_phase: Dict[ExecutionPhase, List[Dict[str, Any]]] = {
        phase: [] for phase in ExecutionPhase
    }
    for rule in rules:
        phase = ExecutionPhase(rule["execution_phase"])
        rules_by_phase[phase].append(rule)

    # Inject dynamic Coverage Rule for Sum Insured
    rules_by_phase[ExecutionPhase.COVERAGE].append({
        "id": "system-coverage-limit",
        "name": "Global Sum Insured Cap",
        "condition": {},  # Always applies
        "action_type": "LIMIT",
        "action_config": {
            "max_amount": base_context["accumulator.available_sum_insured"],
            "accumulator_key": "SUM_INSURED",
            "reason_code": "SUM_INSURED_EXHAUSTED",
            "explanation": "Capped to remaining policy sum insured limit"
        }
    })

    # Track accumulators in memory across line items
    # category_usage is populated from the DB accumulator
    in_memory_accumulators = base_context.get("accumulator.category_usage", {}).copy()
    in_memory_accumulators["SUM_INSURED"] = 0.0

    results = []

    for item in line_items:
        # Build line item specific context
        context = add_line_item_to_context(base_context, item)
        
        financials = {
            "billed_amount": Decimal(str(item.billed_amount)),
            "allowed_amount": Decimal(str(item.billed_amount)),  # Start allowed = billed
            "insurer_payable": Decimal(str(item.billed_amount)),
            "member_payable": Decimal("0.00"),
        }
        
        audit_trail = []
        was_excluded = False

        # Execute through phases
        for phase in [
            ExecutionPhase.EXCLUSION,
            ExecutionPhase.CAPPING,
            ExecutionPhase.COVERAGE,
            ExecutionPhase.COST_SHARING
        ]:
            if was_excluded:
                break  # Skip remaining phases if excluded
                
            for rule in rules_by_phase[phase]:
                # Sync in-memory accumulators into context for this rule evaluation
                for k, v in in_memory_accumulators.items():
                    context[f"accumulator.{k}"] = float(v)
                    
                passed, updated_financials, audit = evaluate_rule(context, rule, financials)
                
                if passed:
                    financials = updated_financials
                    audit_trail.append(audit)
                    
                    # If this was an exclusion rule, mark and break out of all phases
                    if rule["action_type"] == "EXCLUDE":
                        was_excluded = True
                        break
                        
                    # If this rule had an accumulator limit, update the in-memory tracker
                    # NOTE: We only track insurer_payable consumption against the accumulator
                    if rule["action_type"] == "LIMIT":
                        acc_key = rule["action_config"].get("accumulator_key")
                        if acc_key:
                            current_usage = in_memory_accumulators.get(acc_key, Decimal("0.00"))
                            # The impact on the accumulator is the final allowed amount for this item
                            # We use insurer_payable because it reflects what is actually paid out
                            in_memory_accumulators[acc_key] = current_usage + financials["insurer_payable"]

        status = _determine_line_item_status(financials["billed_amount"], financials["insurer_payable"], was_excluded)
        
        results.append({
            "line_item_id": item.id,
            "financials": financials,
            "audit_trail": audit_trail,
            "status": status,
        })

    return results
