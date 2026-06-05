"""Unit tests for the Claims API endpoints."""

import uuid

from fastapi import status


def test_get_claim_not_found(client, override_get_db, mocker):
    """Test fetching a non-existent claim returns 404."""
    # Mock the service to return None
    mocker.patch(
        "src.routes.claims.claim_service.fetch_claim_status",
        return_value=None,
    )
    
    fake_id = uuid.uuid4()
    response = client.get(f"/api/v1/claims/{fake_id}")
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Claim not found."


def test_submit_claim_validation_error(client, override_get_db, mocker):
    """Test claim submission payload schema validation (missing required fields)."""
    # Send an empty payload, should fail Pydantic validation
    response = client.post("/api/v1/claims", json={})
    
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # The detail array should contain validation errors for missing fields
    errors = response.json()["detail"]
    missing_fields = [error["loc"][-1] for error in errors]
    
    assert "policy_id" in missing_fields
    assert "member_id" in missing_fields
    assert "line_items" in missing_fields
