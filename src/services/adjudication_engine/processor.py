"""Processor for the Adjudication Engine."""

import uuid
from decimal import Decimal
from typing import Dict, Any

from sqlalchemy.orm import Session

from src.models.claims import Claim
from src.repositories import claims_repo, policy_repo, rules_repo
from src.serializers.audit import AuditTrailEntry
from src.serializers.claims import ClaimReviewRequest, ReviewAction
from src.services.adjudication_engine.accumulator_manager import apply_claim_to_accumulator, revert_claim_from_accumulator
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

    # 0. Concurrency Check
    if claims_repo.has_pending_claims_for_policy(db, claim.policy_id, exclude_claim_id=claim.id):
        raise ValueError(f"Cannot process claim: Policy {claim.policy_id} has another claim pending manual approval. Please resolve it first.")

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


def execute_manual_review(db: Session, claim_id: uuid.UUID, request: Any) -> Claim:
    """
    Execute manual review decision on a PENDING_APPROVAL claim.
    
    Args:
        db: SQLAlchemy session.
        claim_id: UUID of the claim.
        request: ClaimReviewRequest containing APPROVE or REJECT action.
        
    Returns:
        The updated Claim object.
    """
    # Cast for type hinting
    req: ClaimReviewRequest = request
    
    claim = claims_repo.get_claim_by_id(db, claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found.")
        
    if claim.status != ClaimStatus.PENDING_APPROVAL:
        raise ValueError(f"Claim {claim_id} is not in PENDING_APPROVAL state. Current: {claim.status.value}")
        
    line_items = claims_repo.get_line_items_by_claim_id(db, claim_id)
    
    if req.action == ReviewAction.REJECT:
        # Deny the claim. Preserve line item statuses and payable amounts for history!
        claim.status = ClaimStatus.DENIED
            
    elif req.action == ReviewAction.APPROVE:
        # 1. Fetch accumulator
        accumulator = policy_repo.get_accumulator_by_policy_id(db, claim.policy_id)
        if not accumulator:
            raise ValueError(f"Accumulator for policy {claim.policy_id} not found.")
            
        # 2. Hard-debit sum insured and category usages
        apply_claim_to_accumulator(accumulator, claim, line_items)
                        
        # 4. Determine final claim status
        if claim.total_insurer_payable == Decimal("0.00"):
            # Technically if it's 0, it shouldn't have been approved, but handle gracefully
            claim.status = ClaimStatus.DENIED
        elif claim.total_insurer_payable < claim.total_billed:
            claim.status = ClaimStatus.PARTIALLY_APPROVED
        else:
            claim.status = ClaimStatus.APPROVED

    db.commit()
    db.refresh(claim)
    return claim


def execute_revert_decision(db: Session, claim_id: uuid.UUID) -> Claim:
    """
    Revert a manually reviewed claim and re-adjudicate it.
    
    If the claim was APPROVED or PARTIALLY_APPROVED, reverse the accumulator debits.
    Then, transition the claim to SUBMITTED and re-run the processor to ensure 
    it is evaluated against the current state of policy limits.
    """
    claim = claims_repo.get_claim_by_id(db, claim_id)
    if not claim:
        raise ValueError(f"Claim {claim_id} not found.")
        
    if claim.status not in (ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED, ClaimStatus.DENIED):
        raise ValueError(f"Claim {claim_id} cannot be reverted. Current status: {claim.status.value}")
        
    line_items = claims_repo.get_line_items_by_claim_id(db, claim_id)
    
    # 1. Reverse Accumulator Math if previously approved
    if claim.status in (ClaimStatus.APPROVED, ClaimStatus.PARTIALLY_APPROVED):
        accumulator = policy_repo.get_accumulator_by_policy_id(db, claim.policy_id)
        if not accumulator:
            raise ValueError(f"Accumulator for policy {claim.policy_id} not found.")
            
        revert_claim_from_accumulator(accumulator, claim, line_items)

    # 2. Reset state
    claim.status = ClaimStatus.SUBMITTED

    # 3. Re-adjudicate
    return process_claim(db, claim.id)
