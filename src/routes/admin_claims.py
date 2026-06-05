"""Admin API endpoints for managing and processing claims."""

import uuid
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.repositories import claims_repo
from src.serializers.claims import ClaimStatusResponse
from src.shared.enums import ClaimStatus

from src.services.adjudication_engine.processor import process_claim

router = APIRouter(prefix="/admin/claims", tags=["Admin Claims"])


@router.get(
    "",
    response_model=List[ClaimStatusResponse],
    summary="List all claims",
)
def list_claims(
    status: Optional[ClaimStatus] = Query(None, description="Filter claims by status"),
    db: Session = Depends(get_db),
):
    """Fetch claims, optionally filtering by their current status (e.g. SUBMITTED)."""
    # We will implement the repository method to fetch claims.
    claims = claims_repo.get_claims_by_status(db=db, status_filter=status)
    return [ClaimStatusResponse.model_validate(c) for c in claims]


@router.post(
    "/{claim_id}/process",
    response_model=ClaimStatusResponse,
    summary="Trigger the adjudication pipeline for a claim",
)
def process_claim_endpoint(claim_id: uuid.UUID, db: Session = Depends(get_db)):
    """Run the claim processing and rule engine pipeline.
    
    This manually triggers the backend pipeline to adjudicate the claim, 
    running pre-checks, phase rules, and EOB generation.
    """
    db_claim = claims_repo.get_claim_by_id(db=db, claim_id=claim_id)
    if not db_claim:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found."
        )

    if db_claim.status != ClaimStatus.SUBMITTED:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, 
            detail=f"Only SUBMITTED claims can be processed. Current status: {db_claim.status.value}"
        )

    db_claim = process_claim(db=db, claim_id=claim_id)
    
    return ClaimStatusResponse.model_validate(db_claim)
