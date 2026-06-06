import uuid
from decimal import Decimal
from typing import List

from pydantic import BaseModel

from src.serializers.audit import AuditTrailEntry
from src.shared.enums import ClaimStatus, ServiceCategory


class EOBLineItem(BaseModel):
    """Explanation of Benefits mapping for a single line item."""

    service_category: ServiceCategory
    billed_amount: Decimal
    allowed_amount: Decimal
    insurer_payable: Decimal
    member_payable: Decimal
    status: str
    adjustments: List[AuditTrailEntry]


class EOBResponse(BaseModel):
    """The full Explanation of Benefits document for a claim."""

    claim_id: uuid.UUID
    status: ClaimStatus
    total_billed: Decimal
    total_insurer_payable: Decimal
    total_member_payable: Decimal
    line_items: List[EOBLineItem]

