"""Business logic for handling member disputes."""

import uuid

from sqlalchemy.orm import Session

from src.models.claims import Dispute
from src.repositories import claims_repo, disputes_repo
from src.shared.enums import ClaimStatus, DisputeStatus


def raise_dispute(db: Session, claim_id: uuid.UUID, member_id: uuid.UUID, reason: str) -> Dispute:
    """
    Raise a dispute for an adjudicated claim.
    
    Validates that:
    1. The claim exists.
    2. The member raising the dispute is the member on the claim.
    3. The claim has already completed the manual review process.
    """
    claim = claims_repo.get_claim_by_id(db, claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found.")
        
    if claim.member_id != member_id:
        raise ValueError(f"Member {member_id} is not authorized to dispute claim {claim_id}.")
        
    valid_statuses = {ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED}
    if claim.status not in valid_statuses:
        raise ValueError(f"Disputes can only be raised for reviewed claims. Current status: {claim.status.value}")
        
    return disputes_repo.create_dispute(db, claim_id, member_id, reason)


def update_dispute_status(db: Session, dispute_id: uuid.UUID, status: DisputeStatus) -> Dispute:
    """
    Update the status of a dispute.
    """
    dispute = disputes_repo.update_dispute_status(db, dispute_id, status)
    if not dispute:
        raise ValueError(f"Dispute {dispute_id} not found.")
        
    return dispute
