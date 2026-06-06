"""Shared enum definitions for the claims processing system.

These enums are the single source of truth for all valid categorical
values across the system. They mirror the PostgreSQL enum types defined
in 01_schema.sql exactly.
"""

from __future__ import annotations

import enum


class ServiceCategory(str, enum.Enum):
    """Valid categories for a line item on a hospital bill."""

    ROOM_RENT = "ROOM_RENT"
    ICU_CHARGES = "ICU_CHARGES"
    CONSULTATION = "CONSULTATION"
    OT_CHARGES = "OT_CHARGES"
    PHARMACY = "PHARMACY"
    DIAGNOSTICS = "DIAGNOSTICS"
    DENTAL = "DENTAL"
    AYUSH = "AYUSH"
    CONSUMABLES = "CONSUMABLES"
    COSMETIC = "COSMETIC"
    COSMETIC_SURGERY = "COSMETIC_SURGERY"
    SURGERY = "SURGERY"
    OTHER = "OTHER"


class ClaimType(str, enum.Enum):
    """Type of claim submission channel."""

    REIMBURSEMENT = "REIMBURSEMENT"
    CASHLESS = "CASHLESS"


class ClaimStatus(str, enum.Enum):
    """Pipeline states for a claim."""

    SUBMITTED = "SUBMITTED"
    VALIDATED = "VALIDATED"

    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    PAID = "PAID"


class DisputeStatus(str, enum.Enum):
    """Lifecycle states of a member-initiated dispute."""

    RAISED = "RAISED"
    UNDER_PROCESSING = "UNDER_PROCESSING"
    RESOLVED = "RESOLVED"

class LineItemStatus(str, enum.Enum):
    """Per-line-item adjudication outcome."""

    SUBMITTED = "SUBMITTED"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    EXCLUDED = "EXCLUDED"


class ExecutionPhase(str, enum.Enum):
    """Fixed-order pipeline phases for rule evaluation."""

    EXCLUSION = "EXCLUSION"
    CAPPING = "CAPPING"
    COVERAGE = "COVERAGE"
    COST_SHARING = "COST_SHARING"


class ActionType(str, enum.Enum):
    """The specific financial handler a rule triggers."""

    EXCLUDE = "EXCLUDE"
    LIMIT = "LIMIT"
    COPAY = "COPAY"
    DEDUCTIBLE = "DEDUCTIBLE"


class Gender(str, enum.Enum):
    """Gender values for member profiles."""

    MALE = "MALE"
    FEMALE = "FEMALE"
    OTHER = "OTHER"


class DocumentType(str, enum.Enum):
    """Allowed document types for a claim."""

    BILLS = "BILLS"
    RECEIPTS = "RECEIPTS"
    DISCHARGE_SUMMARY = "DISCHARGE_SUMMARY"
    CLAIM_FORM = "CLAIM_FORM"
    PRESCRIPTIONS = "PRESCRIPTIONS"
    DIAGNOSTIC_REPORTS = "DIAGNOSTIC_REPORTS"
    OTHER = "OTHER"


class LineItemUnit(str, enum.Enum):
    """Standard unit vocabulary for line item metadata.

    Used in the line_items.metadata JSONB field to describe the
    measurement unit of the billed service. The Context Builder uses
    this alongside 'quantity' to compute derived fields like
    per_unit_amount.

    Metadata schema:
        {
            "quantity": <int>,       # Number of units billed (default 1)
            "unit": <LineItemUnit>   # Measurement unit
        }

    Examples by service category:
        ROOM_RENT    → {"quantity": 8, "unit": "DAY"}
        ICU_CHARGES  → {"quantity": 3, "unit": "DAY"}
        NURSING      → {"quantity": 10, "unit": "SHIFT"}
        PHYSIOTHERAPY→ {"quantity": 12, "unit": "SESSION"}
        MEDICINE     → {"quantity": 5, "unit": "STRIP"}
        DIAGNOSTICS  → {"quantity": 3, "unit": "TEST"}
        SURGERY      → {} (atomic — no decomposition needed)
        CONSULTATION → {"quantity": 1, "unit": "VISIT"} or {}
    """

    DAY = "DAY"
    HOUR = "HOUR"
    SESSION = "SESSION"
    VISIT = "VISIT"
    TEST = "TEST"
    STRIP = "STRIP"
    UNIT = "UNIT"
    SHIFT = "SHIFT"

