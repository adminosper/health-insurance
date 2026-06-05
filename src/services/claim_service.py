"""Business logic for the member claim flows."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.claims import Claim
from src.repositories import claims_repo, policy_repo
from src.serializers.claims import ClaimStatusResponse, ClaimSubmitRequest


class ClaimValidationError(Exception):
    """Exception raised for claim validation errors."""


def submit_new_claim(db: Session, request: ClaimSubmitRequest) -> ClaimStatusResponse:
    """Process a new claim submission from a member.
    
    This function validates the policy/member relationship and persists
    the claim in a SUBMITTED state. Actual processing (adjudication)
    is handled asynchronously by a background job.
    """
    # 1. Validate that the policy and member are linked correctly
    is_valid = policy_repo.validate_member_on_policy(
        db=db,
        policy_id=request.policy_id,
        member_id=request.member_id,
    )
    if not is_valid:
        raise ClaimValidationError("Member does not belong to the provided policy.")

    # 2. Persist the initial claim and line items
    # The repository handles the transaction and defaults the status to SUBMITTED
    db_claim = claims_repo.create_claim_with_items(db=db, request=request)

    # 3. Return the status
    return ClaimStatusResponse.model_validate(db_claim)


def fetch_claim_status(db: Session, claim_id: uuid.UUID) -> Optional[ClaimStatusResponse]:
    """Retrieve the high-level status of a claim."""
    db_claim = claims_repo.get_claim_by_id(db=db, claim_id=claim_id)
    if not db_claim:
        return None

    return ClaimStatusResponse.model_validate(db_claim)
