"""Data access logic for policies and members."""

from __future__ import annotations

import uuid
from typing import Optional

from sqlalchemy.orm import Session

from src.models.policies import Member, Policy, Accumulator


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


def get_policy_by_id(db: Session, policy_id: uuid.UUID) -> Optional[Policy]:
    """Fetch a policy by its ID."""
    return db.query(Policy).filter(Policy.id == policy_id).first()


def get_member_by_id(db: Session, member_id: uuid.UUID) -> Optional[Member]:
    """Fetch a member by their ID."""
    return db.query(Member).filter(Member.id == member_id).first()


def get_accumulator_by_policy_id(db: Session, policy_id: uuid.UUID) -> Optional[Accumulator]:
    """Fetch an accumulator by policy ID."""
    return db.query(Accumulator).filter(Accumulator.policy_id == policy_id).first()
