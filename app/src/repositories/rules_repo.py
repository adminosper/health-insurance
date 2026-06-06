"""Data access logic for Rules."""

from __future__ import annotations

import uuid
from typing import List

from sqlalchemy.orm import Session

from src.models.rules import Rule


def get_active_rules_for_plan(db: Session, plan_id: uuid.UUID) -> List[Rule]:
    """Fetch all active rules for a given plan, ordered by phase and priority."""
    return (
        db.query(Rule)
        .filter(Rule.plan_id == plan_id, Rule.is_active == True)
        .order_by(Rule.execution_phase, Rule.priority)
        .all()
    )
