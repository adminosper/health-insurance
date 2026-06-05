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
    QUERY_RAISED = "QUERY_RAISED"
    UNDER_REVIEW = "UNDER_REVIEW"
    ADJUDICATED = "ADJUDICATED"
    PENDING_APPROVAL = "PENDING_APPROVAL"
    APPROVED = "APPROVED"
    PARTIALLY_APPROVED = "PARTIALLY_APPROVED"
    DENIED = "DENIED"
    PAID = "PAID"


class ManualApprovalStatus(str, enum.Enum):
    """Human approver decision states."""

    PENDING = "PENDING"
    APPROVED = "APPROVED"
    OVERRIDDEN = "OVERRIDDEN"
    REJECTED = "REJECTED"


class LineItemStatus(str, enum.Enum):
    """Per-line-item adjudication outcome."""

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
