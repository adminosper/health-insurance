"""SQLAlchemy models for the Rules module."""

from __future__ import annotations

import uuid

from sqlalchemy import Boolean, Column, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import ENUM, JSONB, UUID

from src.database.connection import Base
from src.shared.enums import ActionType, ExecutionPhase


class Rule(Base):
    """Individual adjudication rule tied to a plan."""

    __tablename__ = "rules"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    plan_id = Column(UUID(as_uuid=True), ForeignKey("plans.id"), nullable=False)
    name = Column(String(255), nullable=False)
    execution_phase = Column(ENUM(ExecutionPhase, name="execution_phase", create_type=False), nullable=False)
    priority = Column(Integer, nullable=False)
    condition = Column(JSONB, nullable=False)
    action_type = Column(ENUM(ActionType, name="action_type", create_type=False), nullable=False)
    action_config = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
