"""Tests for dispute API endpoints."""

import uuid
from unittest.mock import patch

from fastapi import status
from fastapi.testclient import TestClient

from main import app
from src.shared.enums import DisputeStatus

client = TestClient(app)


@patch("src.routes.claims.dispute_service.raise_dispute")
def test_raise_dispute_endpoint(mock_raise_dispute):
    claim_id = uuid.uuid4()
    member_id = uuid.uuid4()
    dispute_id = uuid.uuid4()
    
    class MockDispute:
        pass
        
    mock_dispute = MockDispute()
    mock_dispute.id = dispute_id
    mock_dispute.claim_id = claim_id
    mock_dispute.member_id = member_id
    mock_dispute.reason = "The cap is too low."
    mock_dispute.status = DisputeStatus.RAISED
    mock_dispute.created_at = "2025-01-01T00:00:00Z"
        
    mock_raise_dispute.return_value = mock_dispute
    
    response = client.post(
        f"/api/v1/claims/{claim_id}/disputes",
        json={
            "member_id": str(member_id),
            "reason": "The cap is too low."
        }
    )
    
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == str(dispute_id)
    assert data["status"] == DisputeStatus.RAISED.value


@patch("src.routes.admin_claims.dispute_service.update_dispute_status")
def test_update_dispute_status_endpoint(mock_update_dispute):
    dispute_id = uuid.uuid4()
    
    class MockDispute:
        pass
        
    mock_dispute = MockDispute()
    mock_dispute.id = dispute_id
    mock_dispute.claim_id = uuid.uuid4()
    mock_dispute.member_id = uuid.uuid4()
    mock_dispute.reason = "Test"
    mock_dispute.status = DisputeStatus.UNDER_PROCESSING
    mock_dispute.created_at = "2025-01-01T00:00:00Z"
        
    mock_update_dispute.return_value = mock_dispute
    
    response = client.post(
        f"/api/v1/admin/claims/disputes/{dispute_id}/status",
        json={
            "status": "UNDER_PROCESSING"
        }
    )
    
    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["status"] == DisputeStatus.UNDER_PROCESSING.value
