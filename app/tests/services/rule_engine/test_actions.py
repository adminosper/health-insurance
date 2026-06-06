from decimal import Decimal
from src.services.rule_engine.actions import execute_action

def test_exclude_action():
    financials = {
        "billed_amount": Decimal("1000.00"),
        "allowed_amount": Decimal("1000.00"),
        "insurer_payable": Decimal("1000.00"),
        "member_payable": Decimal("0.00")
    }
    
    action_config = {"reason_code": "PERMANENT_EXCLUSION", "explanation": "Excluded"}
    updated, audit = execute_action("EXCLUDE", action_config, financials, {})
    
    assert updated["allowed_amount"] == Decimal("0.00")
    assert updated["insurer_payable"] == Decimal("0.00")
    assert updated["member_payable"] == Decimal("1000.00")
    assert audit["action"] == "EXCLUDE"
    assert audit["amount_impacted"] == 1000.00

def test_limit_action_no_accumulator():
    financials = {
        "billed_amount": Decimal("10000.00"),
        "allowed_amount": Decimal("10000.00"),
        "insurer_payable": Decimal("10000.00"),
        "member_payable": Decimal("0.00")
    }
    
    action_config = {"max_amount": 5000}
    updated, audit = execute_action("LIMIT", action_config, financials, {})
    
    assert updated["allowed_amount"] == Decimal("5000.00")
    assert updated["insurer_payable"] == Decimal("5000.00")
    assert updated["member_payable"] == Decimal("5000.00")
    assert audit["amount_impacted"] == 5000.00

def test_limit_action_with_accumulator():
    financials = {
        "billed_amount": Decimal("10000.00"),
        "allowed_amount": Decimal("10000.00"),
        "insurer_payable": Decimal("10000.00"),
        "member_payable": Decimal("0.00")
    }
    
    # Policy has 500k limit, but already used 495k
    context = {"accumulator.CARDIAC_SURGERY": 495000.00}
    action_config = {"max_amount": 500000, "accumulator_key": "CARDIAC_SURGERY"}
    updated, audit = execute_action("LIMIT", action_config, financials, context)
    
    assert updated["allowed_amount"] == Decimal("5000.00") # capped by remaining balance
    assert updated["insurer_payable"] == Decimal("5000.00")
    assert updated["member_payable"] == Decimal("5000.00")

def test_copay_action():
    financials = {
        "billed_amount": Decimal("1000.00"),
        "allowed_amount": Decimal("1000.00"),
        "insurer_payable": Decimal("1000.00"),
        "member_payable": Decimal("0.00")
    }
    
    action_config = {"percentage": 20}
    updated, audit = execute_action("COPAY", action_config, financials, {})
    
    assert updated["insurer_payable"] == Decimal("800.00")
    assert updated["member_payable"] == Decimal("200.00")
    assert audit["amount_impacted"] == 200.00

def test_deductible_action():
    financials = {
        "billed_amount": Decimal("5000.00"),
        "allowed_amount": Decimal("5000.00"),
        "insurer_payable": Decimal("5000.00"),
        "member_payable": Decimal("0.00")
    }
    
    # 2000 deductible, already paid 500
    context = {"accumulator.active_deductible_paid": 500.00}
    action_config = {"limit": 2000}
    
    updated, audit = execute_action("DEDUCTIBLE", action_config, financials, context)
    
    # Remaining deductible is 1500
    assert updated["insurer_payable"] == Decimal("3500.00")
    assert updated["member_payable"] == Decimal("1500.00")
    assert audit["amount_impacted"] == 1500.00
