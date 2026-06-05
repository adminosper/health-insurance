"""API endpoints for member claim submission and tracking."""

import uuid

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from src.database.connection import get_db
from src.serializers.claims import ClaimStatusResponse, ClaimSubmitRequest
from src.services import claim_service

router = APIRouter(prefix="/claims", tags=["Member Claims"])


@router.post(
    "",
    response_model=ClaimStatusResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a new claim",
)
def submit_claim(request: ClaimSubmitRequest, db: Session = Depends(get_db)):
    """Submit a new claim.
    
    Validates the member and policy, then persists the claim and its
    line items. The claim starts in a SUBMITTED state pending asynchronous
    adjudication.
    """
    try:
        return claim_service.submit_new_claim(db=db, request=request)
    except claim_service.ClaimValidationError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    except Exception as e:
        # Generic catch for unexpected DB or logic errors
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An error occurred while submitting the claim.",
        )


@router.get(
    "/{claim_id}",
    response_model=ClaimStatusResponse,
    summary="Get claim status",
)
def get_claim_status(claim_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the high-level status and financial totals of a claim."""
    claim_response = claim_service.fetch_claim_status(db=db, claim_id=claim_id)
    if not claim_response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    
    return claim_response


@router.get(
    "/{claim_id}/eob",
    summary="Get Explanation of Benefits (EOB)",
)
def get_claim_eob(claim_id: uuid.UUID, db: Session = Depends(get_db)):
    """Fetch the full Explanation of Benefits document for a claim."""
    eob_response = claim_service.generate_eob(db=db, claim_id=claim_id)
    if not eob_response:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Claim not found.")
    
    return eob_response
