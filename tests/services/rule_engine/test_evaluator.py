from src.services.rule_engine.evaluator import evaluate_condition

def test_evaluate_condition_empty():
    assert evaluate_condition({}, {}) is True

def test_evaluate_condition_eq():
    context = {"member.days_active": 35}
    cond = {"field": "member.days_active", "operator": "EQ", "value": 35}
    assert evaluate_condition(context, cond) is True
    
    cond_false = {"field": "member.days_active", "operator": "EQ", "value": 30}
    assert evaluate_condition(context, cond_false) is False

def test_evaluate_condition_gt():
    context = {"member.days_active": 35}
    cond = {"field": "member.days_active", "operator": "GT", "value": 30}
    assert evaluate_condition(context, cond) is True

def test_evaluate_condition_intersects():
    context = {"claim.diagnosis_codes": ["I21", "A01"]}
    cond = {"field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["I21", "I25"]}
    assert evaluate_condition(context, cond) is True
    
    cond_false = {"field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["I50"]}
    assert evaluate_condition(context, cond_false) is False

def test_evaluate_condition_all():
    context = {"member.days_active": 35, "claim.is_accident": False}
    cond = {
        "all": [
            {"field": "member.days_active", "operator": "GT", "value": 30},
            {"field": "claim.is_accident", "operator": "EQ", "value": False}
        ]
    }
    assert evaluate_condition(context, cond) is True
    
    context["claim.is_accident"] = True
    assert evaluate_condition(context, cond) is False

def test_evaluate_condition_not():
    context = {"claim.diagnosis_codes": ["A01"]}
    cond = {
        "not": {
            "field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["I21", "I25"]
        }
    }
    assert evaluate_condition(context, cond) is True
    
    context["claim.diagnosis_codes"] = ["I21"]
    assert evaluate_condition(context, cond) is False
