"""Repository for Dispute data access."""

import uuid

from sqlalchemy.orm import Session

from src.models.claims import Dispute
from src.shared.enums import DisputeStatus


def create_dispute(db: Session, claim_id: uuid.UUID, member_id: uuid.UUID, reason: str) -> Dispute:
    """Create a new dispute for a claim."""
    dispute = Dispute(
        claim_id=claim_id,
        member_id=member_id,
        reason=reason,
        status=DisputeStatus.RAISED,
    )
    db.add(dispute)
    db.commit()
    db.refresh(dispute)
    return dispute


def get_dispute_by_id(db: Session, dispute_id: uuid.UUID) -> Dispute | None:
    """Fetch a dispute by its ID."""
    return db.query(Dispute).filter(Dispute.id == dispute_id).first()


def update_dispute_status(db: Session, dispute_id: uuid.UUID, status: DisputeStatus) -> Dispute | None:
    """Update the status of a dispute."""
    dispute = get_dispute_by_id(db, dispute_id)
    if not dispute:
        return None
        
    dispute.status = status
    db.commit()
    db.refresh(dispute)
    return dispute
