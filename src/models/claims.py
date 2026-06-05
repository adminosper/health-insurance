"""SQLAlchemy models for the Claims module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from src.database.connection import Base
from src.shared.enums import (
    ClaimStatus,
    ClaimType,
    LineItemStatus,
    ManualApprovalStatus,
    ServiceCategory,
)


class Claim(Base):
    """A submitted reimbursement/cashless request."""

    __tablename__ = "claims"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
    member_id = Column(UUID(as_uuid=True), ForeignKey("members.id"), nullable=False)
    diagnosis_codes = Column(String, nullable=False)
    claim_type = Column(ENUM(ClaimType, name="claim_type", create_type=False), nullable=False)
    is_accident = Column(Boolean, nullable=False, default=False)
    admission_date = Column(Date, nullable=False)
    discharge_date = Column(Date, nullable=False)
    status = Column(ENUM(ClaimStatus, name="claim_status", create_type=False), nullable=False, default=ClaimStatus.SUBMITTED)
    manual_approval_status = Column(ENUM(ManualApprovalStatus, name="manual_approval_status", create_type=False), nullable=False, default=ManualApprovalStatus.PENDING)
    total_billed = Column(Numeric(15, 2), nullable=False, default=0)
    total_insurer_payable = Column(Numeric(15, 2), nullable=False, default=0)
    total_member_payable = Column(Numeric(15, 2), nullable=False, default=0)
    documents_attached = Column(JSONB, nullable=False, default=list)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class LineItem(Base):
    """Individual billing entries within a claim."""

    __tablename__ = "line_items"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    claim_id = Column(UUID(as_uuid=True), ForeignKey("claims.id"), nullable=False)
    service_category = Column(ENUM(ServiceCategory, name="service_category", create_type=False), nullable=False)
    billed_amount = Column(Numeric(15, 2), nullable=False)
    allowed_amount = Column(Numeric(15, 2), nullable=False, default=0)
    insurer_payable = Column(Numeric(15, 2), nullable=False, default=0)
    line_item_metadata = Column("metadata", JSONB, nullable=False, default=dict)
    status = Column(ENUM(LineItemStatus, name="line_item_status", create_type=False), nullable=False, default=LineItemStatus.APPROVED)
    audit_trail = Column(JSONB, nullable=False, default=list)
