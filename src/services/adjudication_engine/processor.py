"""Processor for the Adjudication Engine."""

import uuid
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.models.claims import Claim
from src.repositories import claims_repo, policy_repo, rules_repo
from src.serializers.audit import AuditTrailEntry
from src.services.adjudication_engine.context_builder import build_base_context
from src.services.adjudication_engine.pipeline import run_pipeline
from src.services.adjudication_engine.pre_checks import run_pre_adjudication_checks
from src.shared.enums import ActionType, ClaimStatus, ExecutionPhase, LineItemStatus


def _serialize_rules(rules) -> list[Dict[str, Any]]:
    """Convert SQLAlchemy Rule objects to dictionaries for the Rule Engine."""
    serialized = []
    for r in rules:
        serialized.append({
            "id": str(r.id),
            "name": r.name,
            "execution_phase": r.execution_phase.value,
            "condition": r.condition,
            "action_type": r.action_type.value,
            "action_config": r.action_config
        })
    return serialized


def process_claim(db: Session, claim_id: uuid.UUID) -> Claim:
    """
    Main entrypoint for processing a submitted claim.
    
    Args:
        db: SQLAlchemy session.
        claim_id: UUID of the claim to process.
        
    Returns:
        The updated Claim object.
        
    Raises:
        ValueError: If claim is not found or not in SUBMITTED status.
    """
    claim = claims_repo.get_claim_by_id(db, claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found.")
        
    if claim.status != ClaimStatus.SUBMITTED:
        raise ValueError(f"Claim {claim_id} cannot be processed. Current status: {claim.status.value}")

    line_items = claims_repo.get_line_items_by_claim_id(db, claim_id)
    policy = policy_repo.get_policy_by_id(db, claim.policy_id)
    member = policy_repo.get_member_by_id(db, claim.member_id)
    accumulator = policy_repo.get_accumulator_by_policy_id(db, claim.policy_id)

    # 1. Run Pre-checks
    pre_check_passed, pre_check_reason = run_pre_adjudication_checks(claim, policy)
    if not pre_check_passed:
        # Pre-checks failed (e.g. outside tenure, zero billed). Reject claim.
        claim.status = ClaimStatus.DENIED
        for item in line_items:
            item.status = LineItemStatus.DENIED
            item.allowed_amount = Decimal("0.00")
            item.insurer_payable = Decimal("0.00")
            
            audit = AuditTrailEntry(
                step=0,
                rule_name="Pre-Adjudication Check",
                stage=ExecutionPhase.EXCLUSION,
                effect_type=ActionType.EXCLUDE,
                amount_before=item.billed_amount,
                amount_adjusted=-item.billed_amount,
                amount_after=Decimal("0.00"),
                reason_code="PRE_CHECK_FAILED",
                explanation=pre_check_reason
            )
            item.audit_trail = [audit.model_dump(mode="json")]
            
        db.commit()
        return claim

    # 2. Build Base Context
    base_context = build_base_context(db, claim, policy, member, accumulator)

    # 3. Fetch and Serialize Rules
    db_rules = rules_repo.get_active_rules_for_plan(db, policy.plan_id)
    rules = _serialize_rules(db_rules)

    # 4. Run Pipeline
    pipeline_results = run_pipeline(base_context, line_items, rules)

    # 5. Apply Results and Persist
    total_billed = Decimal("0.00")
    total_insurer_payable = Decimal("0.00")
    total_member_payable = Decimal("0.00")

    # The pipeline_results is a list ordered matching the line_items list
    for i, item in enumerate(line_items):
        result = pipeline_results[i]
        fin = result["financials"]
        
        item.allowed_amount = fin["allowed_amount"]
        item.insurer_payable = fin["insurer_payable"]
        item.status = result["status"]
        item.audit_trail = result["audit_trail"]
        
        total_billed += fin["billed_amount"]
        total_insurer_payable += fin["insurer_payable"]
        total_member_payable += fin["member_payable"]

    claim.total_billed = total_billed
    claim.total_insurer_payable = total_insurer_payable
    claim.total_member_payable = total_member_payable
    claim.status = ClaimStatus.PENDING_APPROVAL

    db.commit()
    db.refresh(claim)
    
    return claim
