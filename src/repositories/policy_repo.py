"""Data access logic for policies and members."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.policies import Member, Policy


def validate_member_on_policy(db: Session, policy_id: uuid.UUID, member_id: uuid.UUID) -> bool:
    """Validate that a policy exists and the member belongs to it."""
    # Light validation to ensure relationship holds
    count = (
        db.query(Member)
        .join(Policy, Member.policy_id == Policy.id)
        .filter(Policy.id == policy_id, Member.id == member_id)
        .count()
    )
    return count > 0
