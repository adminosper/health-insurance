"""Business logic for the member claim flows."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.claims import Claim
from src.repositories import claims_repo, policy_repo
from src.serializers.audit import AuditTrailEntry
from src.serializers.claims import ClaimStatusResponse, ClaimSubmitRequest
from src.serializers.eob import EOBLineItem, EOBResponse


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


def generate_eob(db: Session, claim_id: uuid.UUID) -> Optional[EOBResponse]:
    """Compile the Explanation of Benefits for a claim."""
    db_claim = claims_repo.get_claim_by_id(db=db, claim_id=claim_id)
    if not db_claim:
        return None
        
    line_items = claims_repo.get_line_items_by_claim_id(db=db, claim_id=claim_id)
    
    eob_items = []
    for li in line_items:
        adjustments = [AuditTrailEntry.model_validate(audit) for audit in li.audit_trail]
        
        # Calculate member payable per line item manually since we don't store it statically on line item model (we only store insurer_payable and billed)
        # Or wait, member_payable is just billed - insurer_payable
        eob_items.append(
            EOBLineItem(
                service_category=li.service_category,
                billed_amount=li.billed_amount,
                allowed_amount=li.allowed_amount,
                insurer_payable=li.insurer_payable,
                member_payable=li.billed_amount - li.insurer_payable,
                status=li.status,
                adjustments=adjustments
            )
        )
        
    return EOBResponse(
        claim_id=db_claim.id,
        status=db_claim.status,
        total_billed=db_claim.total_billed,
        total_insurer_payable=db_claim.total_insurer_payable,
        total_member_payable=db_claim.total_member_payable,
        line_items=eob_items
    )
