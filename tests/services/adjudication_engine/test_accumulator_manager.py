"""Unit tests for the accumulator manager."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from src.services.adjudication_engine.accumulator_manager import apply_claim_to_accumulator, revert_claim_from_accumulator
from src.shared.enums import LineItemStatus, ServiceCategory, ActionType


def test_accumulator_reversibility_property():
    """
    Test that applying a claim to an accumulator and then immediately reverting it
    results in the exact same mathematical state as the original accumulator.
    """
    # 1. Setup initial accumulator state
    original_sum_insured = Decimal("100000.00")
    original_room_rent_usage = 5000.0
    original_deductible_paid = Decimal("1000.00")
    
    accumulator = MagicMock()
    accumulator.available_sum_insured = original_sum_insured
    accumulator.category_usage = {"ROOM_RENT": original_room_rent_usage}
    accumulator.active_deductible_paid = original_deductible_paid
    
    # 2. Setup claim that will be approved
    claim = MagicMock()
    claim.total_insurer_payable = Decimal("15000.00")
    
    # Line item with $15,000 payable, of which $500 was a deductible
    line_item = MagicMock()
    line_item.status = LineItemStatus.APPROVED
    line_item.service_category = ServiceCategory.ROOM_RENT
    line_item.insurer_payable = Decimal("15000.00")
    line_item.audit_trail = [
        {"effect_type": ActionType.DEDUCTIBLE.value, "amount_adjusted": -500.0}
    ]
    
    # 3. Apply the claim
    apply_claim_to_accumulator(accumulator, claim, [line_item])
    
    # Assert state changed
    assert accumulator.available_sum_insured == Decimal("85000.00")
    assert accumulator.category_usage["ROOM_RENT"] == 20000.0
    assert accumulator.active_deductible_paid == Decimal("1500.00")
    
    # 4. Revert the claim
    revert_claim_from_accumulator(accumulator, claim, [line_item])
    
    # 5. Assert mathematical reversibility
    assert accumulator.available_sum_insured == original_sum_insured
    assert accumulator.category_usage["ROOM_RENT"] == original_room_rent_usage
    assert accumulator.active_deductible_paid == original_deductible_paid
