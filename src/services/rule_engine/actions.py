from decimal import Decimal
from typing import Dict, Any, Tuple

def execute_action(
    action_type: str,
    action_config: Dict[str, Any],
    financials: Dict[str, Decimal],
    context: Dict[str, Any]
) -> Tuple[Dict[str, Decimal], Dict[str, Any]]:
    """
    Executes a financial mutation on the line item financials based on the action type.
    
    Args:
        action_type: One of 'EXCLUDE', 'LIMIT', 'COPAY', 'DEDUCTIBLE'.
        action_config: The JSON configuration for the action.
        financials: Dictionary tracking 'billed_amount', 'allowed_amount', 'insurer_payable', 'member_payable'.
        context: The flattened context object (for resolving accumulators or dynamic fields).
        
    Returns:
        (updated_financials, audit_trail_entry)
    """
    updated = {
        "billed_amount": financials.get("billed_amount", Decimal("0.00")),
        "allowed_amount": financials.get("allowed_amount", Decimal("0.00")),
        "insurer_payable": financials.get("insurer_payable", Decimal("0.00")),
        "member_payable": financials.get("member_payable", Decimal("0.00")),
    }
    
    reason_code = action_config.get("reason_code", action_type)
    explanation = action_config.get("explanation", f"Applied {action_type}")
    amount_impacted = Decimal("0.00")

    if action_type == "EXCLUDE":
        amount_impacted = updated["allowed_amount"]
        if amount_impacted > 0:
            updated["allowed_amount"] = Decimal("0.00")
            updated["insurer_payable"] = Decimal("0.00")
            updated["member_payable"] = updated["billed_amount"]
        
    elif action_type == "LIMIT":
        max_amount = Decimal(str(action_config.get("max_amount", 0)))
        
        # If the limit is specified as a per-unit cap, multiply by the line item's billed quantity
        # This makes the engine unit-agnostic (works for DAY, SESSION, TEST, etc.)
        if action_config.get("limit_type") == "PER_UNIT":
            quantity = Decimal(str(context.get("line_item.quantity", 1)))
            max_amount *= quantity
            
        acc_key = action_config.get("accumulator_key")
        
        if acc_key:
            used_so_far = Decimal(str(context.get(f"accumulator.{acc_key}", 0)))
            available_limit = max(Decimal("0.00"), max_amount - used_so_far)
            cap = min(updated["allowed_amount"], available_limit)
        else:
            cap = min(updated["allowed_amount"], max_amount)
            
        if updated["allowed_amount"] > cap:
            amount_impacted = updated["allowed_amount"] - cap
            updated["allowed_amount"] = cap
            # Reduce insurer payable if it exceeds the new allowed amount
            updated["insurer_payable"] = min(updated["insurer_payable"], updated["allowed_amount"])
            updated["member_payable"] = updated["billed_amount"] - updated["insurer_payable"]

    elif action_type == "COPAY":
        percentage = Decimal(str(action_config.get("percentage", 0)))
        if percentage > 0 and updated["allowed_amount"] > 0:
            copay_amount = (updated["allowed_amount"] * percentage / Decimal("100")).quantize(Decimal("0.01"))
            amount_impacted = min(updated["insurer_payable"], copay_amount)
            updated["insurer_payable"] -= amount_impacted
            updated["member_payable"] += amount_impacted

    elif action_type == "DEDUCTIBLE":
        if "limit_field" in action_config:
            deductible_limit = Decimal(str(context.get(action_config["limit_field"], 0)))
        else:
            deductible_limit = Decimal(str(action_config.get("limit", 0)))
            
        active_paid = Decimal(str(context.get("accumulator.active_deductible_paid", 0)))
        remaining_deductible = max(Decimal("0.00"), deductible_limit - active_paid)
        
        if remaining_deductible > 0 and updated["insurer_payable"] > 0:
            amount_impacted = min(updated["insurer_payable"], remaining_deductible)
            updated["insurer_payable"] -= amount_impacted
            updated["member_payable"] += amount_impacted

    audit_entry = {
        "action": action_type,
        "reason_code": reason_code,
        "explanation": explanation,
        "amount_impacted": float(amount_impacted)
    }

    return updated, audit_entry
