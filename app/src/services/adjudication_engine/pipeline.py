"""Pipeline orchestrator for the Adjudication Engine."""

from decimal import Decimal
from typing import Any, Dict, List

from src.models.claims import LineItem
from src.services.adjudication_engine.context_builder import add_line_item_to_context
from src.services.rule_engine.engine import evaluate_rule
from src.serializers.audit import AuditTrailEntry
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
        step_count = 0
        was_excluded = False
        acc_keys_to_update = set()

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
                
                financials_before = financials.copy()
                passed, updated_financials, action_result = evaluate_rule(context, rule, financials)
                
                if passed:
                    # Collect accumulator keys for deferred update at the end of the line item
                    if rule.get("action_type") == "LIMIT":
                        acc_key = rule.get("action_config", {}).get("accumulator_key")
                        if acc_key:
                            acc_keys_to_update.add(acc_key)
                    
                    # Only log to audit trail if it actually changed the financials or was an exclusion
                    amount_impacted = Decimal(str(action_result.get("amount_impacted", 0)))
                    if amount_impacted > 0 or rule.get("action_type") == "EXCLUDE":
                        step_count += 1
                        financials = updated_financials
                        
                        audit_model = AuditTrailEntry(
                            step=step_count,
                            rule_name=rule["name"],
                            stage=phase,
                            effect_type=action_result["action"],
                            amount_before=Decimal(str(financials_before["insurer_payable"])),
                            amount_adjusted=-amount_impacted,
                            amount_after=financials["insurer_payable"],
                            reason_code=action_result["reason_code"],
                            explanation=action_result["explanation"]
                        )
                        audit_trail.append(audit_model.model_dump(mode="json"))
                        
                        if rule.get("action_type") == "EXCLUDE":
                            was_excluded = True
                            break

        # Now that all phases (including cost sharing) are complete,
        # update the in-memory accumulators with the final insurer_payable amount
        for acc_key in acc_keys_to_update:
            current_usage = in_memory_accumulators.get(acc_key, Decimal("0.00"))
            in_memory_accumulators[acc_key] = Decimal(str(current_usage)) + financials["insurer_payable"]

        status = _determine_line_item_status(financials["billed_amount"], financials["insurer_payable"], was_excluded)
        
        results.append({
            "line_item_id": item.id,
            "financials": financials,
            "audit_trail": audit_trail,
            "status": status,
        })

    return results
