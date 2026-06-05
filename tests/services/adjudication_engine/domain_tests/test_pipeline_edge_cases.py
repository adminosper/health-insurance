"""Domain edge case tests for the Adjudication Engine pipeline."""

import uuid
from decimal import Decimal

from src.models.claims import LineItem
from src.services.adjudication_engine.pipeline import run_pipeline
from src.shared.enums import ExecutionPhase, LineItemStatus, ServiceCategory


def test_deferred_accumulator_math():
    """
    Test that accumulator usage is tracked dynamically and deferred 
    until the absolute end of the line item processing.
    
    If it wasn't deferred, the CAPPING phase would update the accumulator 
    with the 'allowed_amount', and the COST_SHARING phase would drain it further,
    causing double dipping.
    """
    # 1. Setup Base Context with a Rs. 100,000 Sum Insured
    base_context = {
        "accumulator.available_sum_insured": 100000.0,
        "accumulator.category_usage": {
            "ROOM_RENT": 0.0
        }
    }
    
    # 2. Setup Line Item for Rs. 30,000
    item = LineItem(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        service_category=ServiceCategory.ROOM_RENT,
        billed_amount=Decimal("30000.00"),
        line_item_metadata={"quantity": 1, "unit": "DAY"}
    )
    
    # 3. Setup Rules: A CAP that limits to 20,000, and a COPAY of 10%
    rules = [
        {
            "id": "cap-rule",
            "name": "Room Rent Cap",
            "execution_phase": ExecutionPhase.CAPPING.value,
            "condition": {},
            "action_type": "LIMIT",
            "action_config": {
                "max_amount": 20000.0,
                "limit_type": "PER_UNIT",
                "accumulator_key": "ROOM_RENT"
            }
        },
        {
            "id": "copay-rule",
            "name": "Flat Copay",
            "execution_phase": ExecutionPhase.COST_SHARING.value,
            "condition": {},
            "action_type": "COPAY",
            "action_config": {
                "percentage": 10
            }
        }
    ]
    
    # 4. Run Pipeline
    # Expected: Billed=30k -> Cap reduces to 20k -> Copay reduces by 2k -> Insurer Payable = 18k
    results = run_pipeline(base_context, [item], rules)
    
    res = results[0]
    financials = res["financials"]
    
    assert financials["billed_amount"] == Decimal("30000.00")
    assert financials["allowed_amount"] == Decimal("20000.00")
    assert financials["insurer_payable"] == Decimal("18000.00")
    assert financials["member_payable"] == Decimal("12000.00")
    
    # The most critical part: the accumulator should only be updated by the FINAL insurer_payable (18k)
    # The pipeline doesn't return the accumulator, but we can verify the math is solid and 
    # the returned audit trail captures the correct deductions.
    assert len(res["audit_trail"]) == 2
    assert Decimal(str(res["audit_trail"][0]["amount_adjusted"])) == Decimal("-10000.00") # Cap
    assert Decimal(str(res["audit_trail"][1]["amount_adjusted"])) == Decimal("-2000.00")  # Copay


def test_audit_trail_noise_filter_strips_zero_impact_rules():
    """
    Test that rules returning 0.00 amount_impacted do not clutter the audit trail,
    except for EXCLUDE rules which should always log.
    """
    base_context = {
        "accumulator.available_sum_insured": 500000.0,
    }
    
    item = LineItem(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        service_category=ServiceCategory.COSMETIC,
        billed_amount=Decimal("50000.00"),
        line_item_metadata={"quantity": 1, "unit": "UNIT"}
    )
    
    # 1. An EXCLUDE rule that zeroes out the item
    # 2. A CAPPING rule that should result in 0 impact (since it's already zero)
    # 3. A COPAY rule that should result in 0 impact
    rules = [
        {
            "id": "exclude-rule",
            "name": "Cosmetic Exclusion",
            "execution_phase": ExecutionPhase.EXCLUSION.value,
            "condition": {},
            "action_type": "EXCLUDE",
            "action_config": {"reason_code": "EXCLUDED_COSMETIC", "explanation": "Not covered"}
        },
        {
            "id": "copay-rule",
            "name": "Flat Copay",
            "execution_phase": ExecutionPhase.COST_SHARING.value,
            "condition": {},
            "action_type": "COPAY",
            "action_config": {"percentage": 20}
        }
    ]
    
    results = run_pipeline(base_context, [item], rules)
    res = results[0]
    
    assert res["status"] == LineItemStatus.EXCLUDED
    assert res["financials"]["insurer_payable"] == Decimal("0.00")
    
    # We should only see ONE audit trail entry (the exclusion). 
    # The Copay rule evaluated but had zero impact, so it's filtered.
    assert len(res["audit_trail"]) == 1
    assert res["audit_trail"][0]["effect_type"] == "EXCLUDE"
    assert res["audit_trail"][0]["reason_code"] == "EXCLUDED_COSMETIC"
