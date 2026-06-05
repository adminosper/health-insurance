"""Pydantic schemas for the claims API.

This module defines the request and response models for claim submission
and status tracking.
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal
from typing import List

from pydantic import BaseModel, Field

from src.shared.enums import ClaimStatus, ClaimType, DocumentType, ServiceCategory


class LineItemPayload(BaseModel):
    """Payload for a single line item in a claim."""

    service_category: ServiceCategory
    billed_amount: Decimal = Field(..., gt=0, description="Amount billed by the hospital.")


class ClaimSubmitRequest(BaseModel):
    """Payload for submitting a new claim."""

    policy_id: uuid.UUID
    member_id: uuid.UUID
    claim_type: ClaimType
    is_accident: bool = False
    admission_date: date
    discharge_date: date
    diagnosis_codes: List[str] = Field(..., min_length=1)
    documents_attached: List[DocumentType] = Field(default_factory=list)
    line_items: List[LineItemPayload] = Field(..., min_length=1)


class ClaimStatusResponse(BaseModel):
    """Response model for tracking a claim's status."""

    id: uuid.UUID
    status: ClaimStatus
    total_billed: Decimal
    total_insurer_payable: Decimal
    total_member_payable: Decimal

    model_config = {"from_attributes": True}
