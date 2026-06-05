"""Domain edge case tests for the Context Builder."""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from src.models.claims import Claim
from src.models.policies import Accumulator, Member, Policy
from src.services.adjudication_engine.context_builder import build_base_context
from src.shared.enums import ClaimType, Gender


@patch("src.services.adjudication_engine.context_builder.cipher")
@patch("src.services.adjudication_engine.context_builder.claims_repo")
def test_dynamic_effective_balance_deducts_pending_claims(mock_claims_repo, mock_cipher):
    """
    Test that the context builder correctly deducts the sum of all other 
    PENDING_APPROVAL claims from the available_sum_insured to prevent double-spending.
    """
    db_session = MagicMock()
    
    # Mock cipher decryption
    mock_cipher.decrypt_to_list.return_value = ["E11"]
    
    # MOCK: There is another pending claim holding Rs. 2,00,000 for this policy
    mock_claims_repo.get_pending_approval_payable_sum.return_value = Decimal("200000.00")
    
    policy = Policy(
        id=uuid.uuid4(),
        plan_id=uuid.uuid4(),
        chosen_sum_insured=Decimal("500000.00"),
        tenure_start=date(2025, 1, 1),
        tenure_end=date(2026, 1, 1)
    )
    
    member = Member(
        id=uuid.uuid4(),
        policy_id=policy.id,
        date_of_birth=date(1990, 1, 1),
        gender=Gender.MALE,
        relationship="SELF"
    )
    
    accumulator = Accumulator(
        policy_id=policy.id,
        available_sum_insured=Decimal("500000.00"), # DB says 5L available
        category_usage={"ROOM_RENT": 0},
        active_deductible_paid=Decimal("0.00")
    )
    
    claim = Claim(
        id=uuid.uuid4(),
        policy_id=policy.id,
        member_id=member.id,
        claim_type=ClaimType.REIMBURSEMENT,
        diagnosis_codes="encrypted_data",
        admission_date=date(2025, 6, 1),
        discharge_date=date(2025, 6, 5)
    )
    
    # Action: Build Context
    context = build_base_context(db_session, claim, policy, member, accumulator)
    
    # Assert: The effective balance passed to the rule engine should be exactly 3L
    # Because 5L - 2L (pending) = 3L
    assert context["accumulator.available_sum_insured"] == 300000.0
    
    # Assert repository was called with correct policy ID and excluded the current claim
    mock_claims_repo.get_pending_approval_payable_sum.assert_called_once_with(
        db_session, policy.id, exclude_claim_id=claim.id
    )
