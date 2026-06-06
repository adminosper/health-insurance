from decimal import Decimal
from src.services.rule_engine.engine import evaluate_rule

def test_evaluate_rule_condition_fails():
    context = {"member.days_active": 45}
    rule = {
        "id": "123",
        "name": "Initial Waiting Period",
        "condition": {"field": "member.days_active", "operator": "LT", "value": 30},
        "action_type": "EXCLUDE",
        "action_config": {"reason_code": "WAITING"}
    }
    financials = {
        "billed_amount": Decimal("1000.00"),
        "allowed_amount": Decimal("1000.00"),
        "insurer_payable": Decimal("1000.00"),
        "member_payable": Decimal("0.00")
    }
    
    passed, updated_fin, audit = evaluate_rule(context, rule, financials)
    assert passed is False
    assert audit is None
    assert updated_fin["allowed_amount"] == Decimal("1000.00")

def test_evaluate_rule_condition_passes():
    context = {"member.days_active": 15}
    rule = {
        "id": "123",
        "name": "Initial Waiting Period",
        "condition": {"field": "member.days_active", "operator": "LT", "value": 30},
        "action_type": "EXCLUDE",
        "action_config": {"reason_code": "WAITING"}
    }
    financials = {
        "billed_amount": Decimal("1000.00"),
        "allowed_amount": Decimal("1000.00"),
        "insurer_payable": Decimal("1000.00"),
        "member_payable": Decimal("0.00")
    }
    
    passed, updated_fin, audit = evaluate_rule(context, rule, financials)
    assert passed is True
    assert audit is not None
    assert audit["rule_id"] == "123"
    assert audit["rule_name"] == "Initial Waiting Period"
    assert updated_fin["allowed_amount"] == Decimal("0.00")
    assert updated_fin["member_payable"] == Decimal("1000.00")
