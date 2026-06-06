from decimal import Decimal
from typing import Dict, Any, Tuple, Optional
from src.services.rule_engine.evaluator import evaluate_condition
from src.services.rule_engine.actions import execute_action

def evaluate_rule(
    context: Dict[str, Any],
    rule: Dict[str, Any],
    financials: Dict[str, Decimal]
) -> Tuple[bool, Dict[str, Decimal], Optional[Dict[str, Any]]]:
    """
    Evaluates a single rule against the context and applies its action to the financials if the condition passes.
    
    Args:
        context: The flattened context dictionary.
        rule: The rule dictionary (must have 'condition', 'action_type', 'action_config').
        financials: Dictionary tracking 'billed_amount', 'allowed_amount', 'insurer_payable', 'member_payable'.
        
    Returns:
        (condition_passed, updated_financials, audit_trail_entry)
        If condition_passed is False, updated_financials is the same as financials, and audit_trail_entry is None.
    """
    condition = rule.get("condition", {})
    
    if not evaluate_condition(context, condition):
        return False, financials, None
        
    action_type = rule.get("action_type")
    action_config = rule.get("action_config", {})
    
    if not action_type:
        return True, financials, None
        
    updated_financials, audit_entry = execute_action(
        action_type=action_type,
        action_config=action_config,
        financials=financials,
        context=context
    )
    
    # Add rule metadata to audit entry
    audit_entry["rule_id"] = rule.get("id")
    audit_entry["rule_name"] = rule.get("name")
    
    return True, updated_financials, audit_entry
