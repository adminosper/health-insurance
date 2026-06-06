"""SQLAlchemy models for the Plans module."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID

from src.database.connection import Base


class Plan(Base):
    """The insurance product blueprint."""

    __tablename__ = "plans"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    allowed_sum_insured_options = Column(JSONB, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime(timezone=True), nullable=False, default=datetime.utcnow)
