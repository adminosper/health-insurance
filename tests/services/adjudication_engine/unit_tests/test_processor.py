"""Unit tests for the adjudication processor."""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest

from src.services.adjudication_engine.processor import process_claim
from src.shared.enums import ClaimStatus, LineItemStatus


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
    
    # Pre-checks fail
    mocker.patch("src.services.adjudication_engine.processor.run_pre_adjudication_checks", return_value=(False, "Failed checks"))
    
    updated_claim = process_claim(mock_db, mock_claim.id)
    
    assert updated_claim.status == ClaimStatus.DENIED
    assert mock_line_item.status == LineItemStatus.DENIED
    assert mock_line_item.audit_trail[0]["reason_code"] == "PRE_CHECK_FAILED"
