from decimal import Decimal
from pydantic import BaseModel

from src.shared.enums import ActionType, ExecutionPhase


class AuditTrailEntry(BaseModel):
    """A typed representation of a single mutation step on a line item."""

    step: int
    rule_name: str
    stage: ExecutionPhase
    effect_type: ActionType
    amount_before: Decimal
    amount_adjusted: Decimal
    amount_after: Decimal
    reason_code: str
    explanation: str

