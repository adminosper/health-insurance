"""Unit tests for the adjudication processor."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.services.adjudication_engine.processor import process_claim, execute_manual_review
from src.serializers.claims import ClaimReviewRequest, ReviewAction
from src.shared.enums import ClaimStatus, LineItemStatus, ServiceCategory, ActionType


@pytest.fixture
def mock_db():
    return MagicMock()


@pytest.fixture
def mock_claim():
    claim = MagicMock()
    claim.id = uuid.uuid4()
    claim.policy_id = uuid.uuid4()
    claim.member_id = uuid.uuid4()
    claim.status = ClaimStatus.SUBMITTED
    return claim


def test_process_claim_not_found(mock_db, mocker):
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=None)
    with pytest.raises(ValueError, match="not found"):
        process_claim(mock_db, uuid.uuid4())


def test_process_claim_invalid_status(mock_db, mock_claim, mocker):
    mock_claim.status = ClaimStatus.PENDING_APPROVAL
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=mock_claim)
    with pytest.raises(ValueError, match="Current status"):
        process_claim(mock_db, mock_claim.id)


def test_process_claim_pre_check_fails(mock_db, mock_claim, mocker):
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=mock_claim)
    
    mock_line_item = MagicMock()
    mock_line_item.billed_amount = Decimal("100.00")
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_line_items_by_claim_id", return_value=[mock_line_item])
    mocker.patch("src.services.adjudication_engine.processor.policy_repo.get_policy_by_id")
    mocker.patch("src.services.adjudication_engine.processor.policy_repo.get_member_by_id")
    mocker.patch("src.services.adjudication_engine.processor.policy_repo.get_accumulator_by_policy_id")
    
    # Mock concurrency check
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.has_pending_claims_for_policy", return_value=False)
    
    # Pre-checks fail
    mocker.patch("src.services.adjudication_engine.processor.run_pre_adjudication_checks", return_value=(False, "Failed checks"))
    
    updated_claim = process_claim(mock_db, mock_claim.id)
    
    assert updated_claim.status == ClaimStatus.DENIED
    assert mock_line_item.status == LineItemStatus.DENIED
    assert mock_line_item.audit_trail[0]["reason_code"] == "PRE_CHECK_FAILED"


def test_execute_manual_review_reject(mock_db, mock_claim, mocker):
    mock_claim.status = ClaimStatus.PENDING_APPROVAL
    mock_claim.total_insurer_payable = Decimal("500.00")
    
    mock_line = MagicMock()
    mock_line.insurer_payable = Decimal("500.00")
    mock_line.status = LineItemStatus.PARTIALLY_APPROVED
    
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=mock_claim)
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_line_items_by_claim_id", return_value=[mock_line])
    
    req = ClaimReviewRequest(action=ReviewAction.REJECT)
    
    res = execute_manual_review(mock_db, mock_claim.id, req)
    
    assert res.status == ClaimStatus.DENIED
    # Line items should NOT be overridden to DENIED, so they preserve engine state
    assert mock_line.status == LineItemStatus.PARTIALLY_APPROVED
    # We DO NOT zero out the payable amounts for historical record!
    assert mock_claim.total_insurer_payable == Decimal("500.00")
    assert mock_line.insurer_payable == Decimal("500.00")


def test_execute_manual_review_approve(mock_db, mock_claim, mocker):
    mock_claim.status = ClaimStatus.PENDING_APPROVAL
    mock_claim.policy_id = uuid.uuid4()
    mock_claim.total_insurer_payable = Decimal("1000.00")
    mock_claim.total_billed = Decimal("1500.00")
    
    mock_line = MagicMock()
    mock_line.service_category = ServiceCategory.ROOM_RENT
    mock_line.insurer_payable = Decimal("1000.00")
    mock_line.status = LineItemStatus.APPROVED
    mock_line.audit_trail = [
        {"effect_type": ActionType.DEDUCTIBLE.value, "amount_adjusted": -500.0}
    ]
    
    mock_accumulator = MagicMock()
    mock_accumulator.available_sum_insured = Decimal("50000.00")
    mock_accumulator.category_usage = {"ROOM_RENT": 0.0}
    mock_accumulator.active_deductible_paid = Decimal("0.00")
    
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=mock_claim)
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_line_items_by_claim_id", return_value=[mock_line])
    mocker.patch("src.services.adjudication_engine.processor.policy_repo.get_accumulator_by_policy_id", return_value=mock_accumulator)
    
    req = ClaimReviewRequest(action=ReviewAction.APPROVE)
    
    res = execute_manual_review(mock_db, mock_claim.id, req)
    
    assert res.status == ClaimStatus.PARTIALLY_APPROVED
    assert mock_accumulator.available_sum_insured == Decimal("49000.00")
    assert mock_accumulator.category_usage["ROOM_RENT"] == 1000.0
    assert mock_accumulator.active_deductible_paid == Decimal("500.0")


def test_execute_revert_decision(mock_db, mock_claim, mocker):
    from src.services.adjudication_engine.processor import execute_revert_decision
    
    mock_claim.status = ClaimStatus.APPROVED
    mock_claim.policy_id = uuid.uuid4()
    mock_claim.total_insurer_payable = Decimal("1000.00")
    
    mock_line = MagicMock()
    mock_line.service_category = ServiceCategory.ROOM_RENT
    mock_line.insurer_payable = Decimal("1000.00")
    mock_line.status = LineItemStatus.APPROVED
    mock_line.audit_trail = [
        {"effect_type": ActionType.DEDUCTIBLE.value, "amount_adjusted": -500.0}
    ]
    
    mock_accumulator = MagicMock()
    mock_accumulator.available_sum_insured = Decimal("49000.00")
    mock_accumulator.category_usage = {"ROOM_RENT": 1000.0}
    mock_accumulator.active_deductible_paid = Decimal("500.00")
    
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_claim_by_id", return_value=mock_claim)
    mocker.patch("src.services.adjudication_engine.processor.claims_repo.get_line_items_by_claim_id", return_value=[mock_line])
    mocker.patch("src.services.adjudication_engine.processor.policy_repo.get_accumulator_by_policy_id", return_value=mock_accumulator)
    
    # Mock process_claim to return the claim untouched for testing
    mocker.patch("src.services.adjudication_engine.processor.process_claim", return_value=mock_claim)
    
    res = execute_revert_decision(mock_db, mock_claim.id)
    
    # Assert accumulator is accurately reversed
    assert mock_accumulator.available_sum_insured == Decimal("50000.00")
    assert mock_accumulator.category_usage["ROOM_RENT"] == 0.0
    assert mock_accumulator.active_deductible_paid == Decimal("0.00")
    # Assert status was set to SUBMITTED before re-adjudicating
    assert res.status == ClaimStatus.SUBMITTED
