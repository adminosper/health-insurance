"""SQLAlchemy models for the Policies module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Column, Date, DateTime, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from src.database.connection import Base
from src.shared.enums import Gender


class Policy(Base):
    """A purchased contract tied to a plan."""

    __tablename__ = "policies"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    chosen_sum_insured = Column(Numeric(15, 2), nullable=False)
    tenure_start = Column(Date, nullable=False)
    tenure_end = Column(Date, nullable=False)
    policyholder_name = Column(String(255), nullable=False)
    policyholder_contact = Column(JSONB, nullable=True)
    policyholder_kyc = Column(JSONB, nullable=True)
    bank_account_details = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)


class Member(Base):
    """An individual covered under a policy."""

    __tablename__ = "members"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), nullable=False)
    full_name = Column(String(255), nullable=False)
    date_of_birth = Column(Date, nullable=False)
    gender = Column(ENUM(Gender, name="gender", create_type=False), nullable=False)
    relationship = Column(String(50), nullable=False)
    ped_list = Column(JSONB, nullable=False, default=list)


class Accumulator(Base):
    """Dynamic financial state per policy."""

    __tablename__ = "accumulators"

    policy_id = Column(UUID(as_uuid=True), ForeignKey("policies.id"), primary_key=True)
    available_sum_insured = Column(Numeric(15, 2), nullable=False)
    accumulated_ncb = Column(Numeric(15, 2), nullable=False, default=0)
    active_deductible_paid = Column(Numeric(15, 2), nullable=False, default=0)
    category_usage = Column(JSONB, nullable=False, default=dict)
