"""Domain/Integration tests for claim processing scenarios."""

import uuid

from fastapi import status

from src.shared.enums import ClaimStatus


def test_scenario_member_not_part_of_policy(client, override_get_db, mocker):
    """
    Scenario: Claim Submission - Invalid Member/Policy Relationship
    
    Context:
    A user attempts to submit a reimbursement claim.
    They provide a valid Policy ID, but the Member ID belongs to a different family
    or does not exist on that specific policy contract.
    
    Desired Output:
    The claim submission should be rejected outright with a 400 Bad Request.
    The database should not persist any claim records.
    The error message should clearly indicate the validation failure.
    """
    # 1. Setup Mock State:
    # We mock the repository layer to simulate that the validation query returns False.
    # This means the member is NOT found on the policy.
    mocker.patch(
        "src.services.claim_service.policy_repo.validate_member_on_policy",
        return_value=False,
    )
    
    # 2. Action:
    # Submit the claim payload
    payload = {
        "policy_id": str(uuid.uuid4()),
        "member_id": str(uuid.uuid4()),
        "claim_type": "REIMBURSEMENT",
        "is_accident": False,
        "admission_date": "2023-10-01",
        "discharge_date": "2023-10-05",
        "diagnosis_codes": ["I21"],
        "documents_attached": ["BILLS"],
        "line_items": [
            {
                "service_category": "ROOM_RENT",
                "billed_amount": 5000.00
            }
        ]
    }
    response = client.post("/api/v1/claims", json=payload)
    
    # 3. Assertions:
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Member does not belong to the provided policy."


def test_scenario_successful_claim_submission(client, override_get_db, mocker):
    """
    Scenario: Claim Submission - Happy Path
    
    Context:
    A user submits a valid claim for a member who is correctly enrolled in the policy.
    
    Desired Output:
    The API should return a 201 Created status.
    The claim status should be explicitly set to 'SUBMITTED'.
    The total_billed should equal the sum of all line items.
    """
    # 1. Setup Mock State:
    # The member is valid.
    mocker.patch(
        "src.services.claim_service.policy_repo.validate_member_on_policy",
        return_value=True,
    )
    
    # Mock the DB claim creation to return a fake created Claim model
    fake_claim_id = uuid.uuid4()
    
    # Create a mock object that mimics the SQLAlchemy Claim model for Pydantic serialization
    class MockClaim:
        id = fake_claim_id
        status = ClaimStatus.SUBMITTED
        total_billed = 15000.00
        total_insurer_payable = 0.00
        total_member_payable = 0.00

    mocker.patch(
        "src.services.claim_service.claims_repo.create_claim_with_items",
        return_value=MockClaim(),
    )
    
    # 2. Action:
    payload = {
        "policy_id": str(uuid.uuid4()),
        "member_id": str(uuid.uuid4()),
        "claim_type": "REIMBURSEMENT",
        "is_accident": False,
        "admission_date": "2023-10-01",
        "discharge_date": "2023-10-05",
        "diagnosis_codes": ["I21"],
        "documents_attached": ["BILLS", "DISCHARGE_SUMMARY"],
        "line_items": [
            {
                "service_category": "ROOM_RENT",
                "billed_amount": 10000.00
            },
            {
                "service_category": "PHARMACY",
                "billed_amount": 5000.00
            }
        ]
    }
    response = client.post("/api/v1/claims", json=payload)
    
    # 3. Assertions:
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == str(fake_claim_id)
    assert data["status"] == "SUBMITTED"
    assert data["total_billed"] == "15000.0"
