from typing import Any, Dict

def resolve_field(context: Dict[str, Any], field_path: str) -> Any:
    """Resolve a dot-separated field path against the flattened context dictionary."""
    return context.get(field_path)

def evaluate_condition(context: Dict[str, Any], condition: Dict[str, Any]) -> bool:
    """Evaluate a JSON DSL condition against the context."""
    if not condition:
        return True  # Empty condition always passes

    if "all" in condition:
        return all(evaluate_condition(context, c) for c in condition["all"])
    
    if "any" in condition:
        return any(evaluate_condition(context, c) for c in condition["any"])

    if "not" in condition:
        return not evaluate_condition(context, condition["not"])

    field = condition.get("field")
    operator = condition.get("operator")
    target_value = condition.get("value")

    if not field or not operator:
        return False

    actual_value = resolve_field(context, field)
    
    return evaluate_operator(actual_value, operator, target_value)

def evaluate_operator(actual: Any, operator: str, target: Any) -> bool:
    if actual is None:
        if operator == "NEQ":
            return True
        if operator == "NOT_IN":
            return True
        return False

    if operator == "EQ":
        return actual == target
    if operator == "NEQ":
        return actual != target
    if operator == "GT":
        return actual > target
    if operator == "GTE":
        return actual >= target
    if operator == "LT":
        return actual < target
    if operator == "LTE":
        return actual <= target
    if operator == "IN":
        if not isinstance(target, list):
            return False
        return actual in target
    if operator == "NOT_IN":
        if not isinstance(target, list):
            return False
        return actual not in target
    if operator == "INTERSECTS":
        # Target must be a list. Actual can be a list (like diagnosis_codes parsed or raw string)
        # Assuming actual and target are lists or strings that can be converted to lists
        if not isinstance(target, list):
            return False
        actual_list = actual if isinstance(actual, list) else [actual]
        return bool(set(actual_list) & set(target))

    return False
