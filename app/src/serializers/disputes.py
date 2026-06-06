"""Pydantic schemas for the disputes API."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from src.shared.enums import DisputeStatus


class DisputeCreateRequest(BaseModel):
    """Payload for a member raising a dispute."""

    member_id: uuid.UUID
    reason: str = Field(..., min_length=10, description="The detailed reason for disputing the adjudication.")


class DisputeStatusUpdateRequest(BaseModel):
    """Payload for an admin updating a dispute status."""

    status: DisputeStatus


class DisputeResponse(BaseModel):
    """Response model for a dispute."""

    id: uuid.UUID
    claim_id: uuid.UUID
    member_id: uuid.UUID
    reason: str
    status: DisputeStatus
    created_at: datetime

    model_config = {"from_attributes": True}
