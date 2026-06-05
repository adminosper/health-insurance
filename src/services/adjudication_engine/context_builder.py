"""Context Builder for Adjudication Engine."""

from datetime import date
from typing import Any, Dict

from sqlalchemy.orm import Session

from src.models.claims import Claim, LineItem
from src.models.policies import Accumulator, Member, Policy
from src.repositories import claims_repo
from src.utils.crypto import cipher


def _get_member_age(dob: date) -> int:
    today = date.today()
    return today.year - dob.year - ((today.month, today.day) < (dob.month, dob.day))


def build_base_context(
    db: Session,
    claim: Claim,
    policy: Policy,
    member: Member,
    accumulator: Accumulator,
) -> Dict[str, Any]:
    """Build the base flat context object without line item specifics.
    
    This decrypts diagnosis codes and calculates dynamic fields like member.age 
    and effective accumulator balance.
    """
    # Calculate Effective Balance
    pending_sum = claims_repo.get_pending_approval_payable_sum(db, policy.id, exclude_claim_id=claim.id)
    effective_si = accumulator.available_sum_insured - pending_sum

    # Decrypt diagnosis codes
    decrypted_codes = cipher.decrypt_to_list(claim.diagnosis_codes)

    # Calculate computed fields
    age = _get_member_age(member.date_of_birth)
    days_active = (date.today() - policy.tenure_start).days

    return {
        "policy.plan_id": str(policy.plan_id),
        "policy.chosen_sum_insured": float(policy.chosen_sum_insured),
        "policy.tenure_start": str(policy.tenure_start),
        "policy.tenure_end": str(policy.tenure_end),
        
        "member.age": age,
        "member.gender": member.gender.value,
        "member.ped_codes": member.ped_list,
        "member.days_active": days_active,
        "member.relationship": member.relationship,
        
        "claim.diagnosis_codes": decrypted_codes,
        "claim.is_accident": claim.is_accident,
        "claim.admission_date": str(claim.admission_date),
        "claim.discharge_date": str(claim.discharge_date),
        "claim.claim_type": claim.claim_type.value,
        
        "accumulator.available_sum_insured": float(effective_si),
        "accumulator.category_usage": accumulator.category_usage.copy(),
        "accumulator.active_deductible_paid": float(accumulator.active_deductible_paid),
    }


def add_line_item_to_context(base_context: Dict[str, Any], line_item: LineItem) -> Dict[str, Any]:
    """Create a copy of the base context and add line item specific fields.
    
    Extracts structured metadata (quantity, unit) and computes derived fields
    like per_unit_amount for use in rule conditions and the Pipeline normalizer.
    """
    context = base_context.copy()
    context["line_item.service_category"] = line_item.service_category.value
    context["line_item.billed_amount"] = float(line_item.billed_amount)

    # Extract metadata — defaults for atomic line items (no decomposition)
    meta = line_item.line_item_metadata or {}
    quantity = meta.get("quantity", 1)
    unit = meta.get("unit", "UNIT")

    context["line_item.quantity"] = quantity
    context["line_item.unit"] = unit

    if quantity > 0:
        context["line_item.per_unit_amount"] = float(line_item.billed_amount) / quantity
    else:
        context["line_item.per_unit_amount"] = float(line_item.billed_amount)

    return context
