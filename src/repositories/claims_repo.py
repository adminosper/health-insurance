"""Data access logic for claims and line items."""

from __future__ import annotations

import uuid
from decimal import Decimal
from typing import Optional

from sqlalchemy import func
from sqlalchemy.orm import Session

from src.models.claims import Claim, LineItem
from src.serializers.claims import ClaimSubmitRequest
from src.shared.enums import ClaimStatus
from src.utils.crypto import cipher


def create_claim_with_items(db: Session, request: ClaimSubmitRequest) -> Claim:
    """Persist a new claim and its line items to the database."""
    total_billed = sum(item.billed_amount for item in request.line_items)

    db_claim = Claim(
        policy_id=request.policy_id,
        member_id=request.member_id,
        claim_type=request.claim_type,
        is_accident=request.is_accident,
        admission_date=request.admission_date,
        discharge_date=request.discharge_date,
        diagnosis_codes=cipher.encrypt_list(request.diagnosis_codes),
        documents_attached=[doc.value for doc in request.documents_attached],
        total_billed=total_billed,
        status=ClaimStatus.SUBMITTED,
    )
    db.add(db_claim)
    db.flush()  # To generate db_claim.id

    for item in request.line_items:
        db_line_item = LineItem(
            claim_id=db_claim.id,
            service_category=item.service_category,
            billed_amount=item.billed_amount,
            line_item_metadata=item.metadata.model_dump(),
        )
        db.add(db_line_item)

    db.commit()
    db.refresh(db_claim)
    return db_claim


def get_claim_by_id(db: Session, claim_id: uuid.UUID) -> Optional[Claim]:
    """Fetch a claim by its ID."""
    return db.query(Claim).filter(Claim.id == claim_id).first()


def get_line_items_by_claim_id(db: Session, claim_id: uuid.UUID) -> list[LineItem]:
    """Fetch all line items for a specific claim."""
    return db.query(LineItem).filter(LineItem.claim_id == claim_id).all()


def get_claims_by_status(db: Session, status_filter: Optional[ClaimStatus] = None) -> list[Claim]:
    """Fetch a list of claims, optionally filtered by their status."""
    query = db.query(Claim)
    if status_filter:
        query = query.filter(Claim.status == status_filter)
    return query.order_by(Claim.created_at.desc()).all()


def get_pending_approval_payable_sum(db: Session, policy_id: uuid.UUID, exclude_claim_id: uuid.UUID) -> Decimal:
    """Calculate the total insurer payable for all PENDING_APPROVAL claims on a policy.
    
    Excludes the current claim being adjudicated.
    Used for dynamic effective accumulator calculation.
    """
    total = db.query(func.sum(Claim.total_insurer_payable)).filter(
        Claim.policy_id == policy_id,
        Claim.status == ClaimStatus.PENDING_APPROVAL,
        Claim.id != exclude_claim_id
    ).scalar()
    
    return total or Decimal(0)


