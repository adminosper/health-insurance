"""Data access logic for claims and line items."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.claims import Claim, LineItem
from src.serializers.claims import ClaimSubmitRequest
from src.shared.enums import ClaimStatus


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
        diagnosis_codes=request.diagnosis_codes,
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
        )
        db.add(db_line_item)

    db.commit()
    db.refresh(db_claim)
    return db_claim


def get_claim_by_id(db: Session, claim_id: uuid.UUID) -> Optional[Claim]:
    """Fetch a claim by its ID."""
    return db.query(Claim).filter(Claim.id == claim_id).first()
