"""Unit tests for dispute service logic."""

import uuid
from unittest.mock import MagicMock, patch
import pytest

from src.services.dispute_service import raise_dispute
from src.shared.enums import ClaimStatus


@pytest.fixture
def mock_db():
    return MagicMock()


@patch("src.services.dispute_service.claims_repo")
@patch("src.services.dispute_service.disputes_repo")
def test_raise_dispute_success(mock_disputes_repo, mock_claims_repo, mock_db):
    claim_id = uuid.uuid4()
    member_id = uuid.uuid4()
    
    mock_claim = MagicMock()
    mock_claim.member_id = member_id
    mock_claim.status = ClaimStatus.APPROVED
    mock_claims_repo.get_claim_by_id.return_value = mock_claim
    
    mock_dispute = MagicMock()
    mock_disputes_repo.create_dispute.return_value = mock_dispute
    
    result = raise_dispute(mock_db, claim_id, member_id, "Incorrect rule applied.")
    
    assert result == mock_dispute
    mock_disputes_repo.create_dispute.assert_called_once_with(mock_db, claim_id, member_id, "Incorrect rule applied.")


@patch("src.services.dispute_service.claims_repo")
def test_raise_dispute_claim_not_found(mock_claims_repo, mock_db):
    mock_claims_repo.get_claim_by_id.return_value = None
    
    with pytest.raises(ValueError, match="Claim .* not found"):
        raise_dispute(mock_db, uuid.uuid4(), uuid.uuid4(), "Test reason")


@patch("src.services.dispute_service.claims_repo")
def test_raise_dispute_wrong_member(mock_claims_repo, mock_db):
    mock_claim = MagicMock()
    mock_claim.member_id = uuid.uuid4()
    mock_claims_repo.get_claim_by_id.return_value = mock_claim
    
    with pytest.raises(ValueError, match="is not authorized to dispute claim"):
        raise_dispute(mock_db, uuid.uuid4(), uuid.uuid4(), "Test reason")


@patch("src.services.dispute_service.claims_repo")
def test_raise_dispute_invalid_status(mock_claims_repo, mock_db):
    member_id = uuid.uuid4()
    mock_claim = MagicMock()
    mock_claim.member_id = member_id
    mock_claim.status = ClaimStatus.SUBMITTED
    mock_claims_repo.get_claim_by_id.return_value = mock_claim
    
    with pytest.raises(ValueError, match="Disputes can only be raised for reviewed claims"):
        raise_dispute(mock_db, uuid.uuid4(), member_id, "Test reason")
