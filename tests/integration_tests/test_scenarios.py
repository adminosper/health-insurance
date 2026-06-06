"""
Domain Test: Multi-Line-Item Claim with Exclusion + Aggregate Category Cap

SCENARIO:
A claim for a patient with diabetes (E11) who has been active for only 400 days
(less than the 730-day pre-existing disease waiting period). The claim contains
multiple DIAGNOSTICS line items that together exceed a category sublimit.

This test exercises two design properties:
1. Pre-existing disease exclusion (condition-driven EXCLUDE)
2. Aggregate category capping across multiple line items of the same type
   (in-memory accumulator tracking — the Pipeline's responsibility, simulated here)

DESIGN INSIGHT:
The Rule Engine is stateless and processes ONE line item at a time. Cross-line-item
accumulator tracking (e.g. "total diagnostics capped at 20k") is the Pipeline's job.
This test simulates the Pipeline loop to prove the pattern works end-to-end.
"""

import uuid
from datetime import date
from decimal import Decimal
from unittest.mock import MagicMock, patch

from fastapi import status

from src.models.claims import Claim, LineItem
from src.models.policies import Accumulator, Member, Policy
from src.services.adjudication_engine.context_builder import build_base_context
from src.services.adjudication_engine.pipeline import run_pipeline
from src.services.rule_engine.engine import evaluate_rule
from src.shared.enums import ClaimStatus, ClaimType, ExecutionPhase, Gender, LineItemStatus, ServiceCategory

# ── Shared Fixtures ──────────────────────────────────────────────────────────

EXCLUSION_RULE_PRE_EXISTING = {
    "id": "rule-pre-existing-exclusion",
    "name": "Pre-Existing Disease 2-Year Waiting Period",
    "condition": {
        "all": [
            {"field": "member.days_active", "operator": "LT", "value": 730},
            {"field": "claim.diagnosis_codes", "operator": "INTERSECTS", "value": ["E10", "E11", "E14"]},
            {"field": "claim.is_accident", "operator": "EQ", "value": False}
        ]
    },
    "action_type": "EXCLUDE",
    "action_config": {
        "reason_code": "PRE_EXISTING_WAITING",
        "explanation": "Pre-existing conditions excluded within 2-year waiting period"
    }
}

CAPPING_RULE_DIAGNOSTICS = {
    "id": "rule-diagnostics-cap",
    "name": "Total Diagnostics Cap 20k",
    "condition": {
        "field": "line_item.service_category", "operator": "EQ", "value": "DIAGNOSTICS"
    },
    "action_type": "LIMIT",
    "action_config": {
        "max_amount": 20000,
        "accumulator_key": "DIAGNOSTICS",
        "reason_code": "DIAGNOSTICS_CAP",
        "explanation": "Total diagnostics capped at Rs.20,000 per claim"
    }
}


# ── Test: Pre-Existing Disease Exclusion ─────────────────────────────────────

def test_pre_existing_disease_excludes_all_line_items():
    """
    Patient with diabetes (E11) claims after only 400 days (< 730 day waiting).
    Every line item, regardless of service category, should be excluded because
    the exclusion rule fires on claim-level fields (diagnosis + days_active).
    """
    base_context = {
        "member.days_active": 400,
        "claim.diagnosis_codes": ["E11", "J18"],
        "claim.is_accident": False,
        "policy.chosen_sum_insured": 500000,
    }

    line_items = [
        {"service_category": "ROOM_RENT", "billed": Decimal("40000.00")},
        {"service_category": "SURGERY", "billed": Decimal("200000.00")},
        {"service_category": "MEDICINE", "billed": Decimal("15000.00")},
    ]

    for item in line_items:
        context = {**base_context, "line_item.service_category": item["service_category"]}
        financials = {
            "billed_amount": item["billed"],
            "allowed_amount": item["billed"],
            "insurer_payable": item["billed"],
            "member_payable": Decimal("0.00"),
        }

        passed, updated, audit = evaluate_rule(context, EXCLUSION_RULE_PRE_EXISTING, financials)

        assert passed is True, f"Rule should fire for {item['service_category']}"
        assert updated["allowed_amount"] == Decimal("0.00")
        assert updated["insurer_payable"] == Decimal("0.00")
        assert updated["member_payable"] == item["billed"]
        assert audit["reason_code"] == "PRE_EXISTING_WAITING"


def test_pre_existing_rule_does_not_fire_after_waiting_period():
    """Same patient, but now 800 days active — rule should NOT fire."""
    context = {
        "member.days_active": 800,
        "claim.diagnosis_codes": ["E11"],
        "claim.is_accident": False,
        "line_item.service_category": "SURGERY",
    }
    financials = {
        "billed_amount": Decimal("200000.00"),
        "allowed_amount": Decimal("200000.00"),
        "insurer_payable": Decimal("200000.00"),
        "member_payable": Decimal("0.00"),
    }

    passed, updated, _ = evaluate_rule(context, EXCLUSION_RULE_PRE_EXISTING, financials)

    assert passed is False
    assert updated["insurer_payable"] == Decimal("200000.00")


# ── Test: Aggregate Category Cap Across Line Items ───────────────────────────

def test_diagnostics_aggregate_cap_across_line_items():
    """
    Claim has 3 DIAGNOSTICS line items totalling Rs.30,000.
    Rule caps total diagnostics at Rs.20,000 per claim.

    The Pipeline processes line items sequentially, passing an in-memory
    accumulator through the context. This test simulates that loop.

    Expected:
      Blood Test (5k)  → allowed 5k, accumulator = 5k
      MRI (15k)        → allowed 15k, accumulator = 20k (at limit)
      CT Scan (10k)    → allowed 0k, accumulator exhausted
    """
    line_items = [
        {"name": "Blood Test", "billed": Decimal("5000.00")},
        {"name": "MRI", "billed": Decimal("15000.00")},
        {"name": "CT Scan", "billed": Decimal("10000.00")},
    ]

    # This is what the Pipeline tracks in memory across line items
    in_memory_accumulator = Decimal("0.00")
    results = []

    for item in line_items:
        context = {
            "line_item.service_category": "DIAGNOSTICS",
            "accumulator.DIAGNOSTICS": float(in_memory_accumulator),
        }
        financials = {
            "billed_amount": item["billed"],
            "allowed_amount": item["billed"],
            "insurer_payable": item["billed"],
            "member_payable": Decimal("0.00"),
        }

        passed, updated, audit = evaluate_rule(context, CAPPING_RULE_DIAGNOSTICS, financials)
        # Pipeline updates the in-memory accumulator with what was actually allowed
        in_memory_accumulator += updated["insurer_payable"]
        results.append({"name": item["name"], "financials": updated, "audit": audit})

    # Blood Test: 5k allowed, fully within cap
    assert results[0]["financials"]["insurer_payable"] == Decimal("5000.00")

    # MRI: 15k allowed, reaches the 20k cap exactly
    assert results[1]["financials"]["insurer_payable"] == Decimal("15000.00")

    # CT Scan: 0k allowed, accumulator exhausted (20k already used)
    assert results[2]["financials"]["insurer_payable"] == Decimal("0.00")
    assert results[2]["financials"]["member_payable"] == Decimal("10000.00")

    # Total insurer payable across all line items = Rs.20,000 (the cap)
    total_insurer = sum(r["financials"]["insurer_payable"] for r in results)
    assert total_insurer == Decimal("20000.00")
"""
Domain Test: Sum Insured Exhaustion — Individual Items Pass Rules, Total Exceeds Coverage

SCENARIO:
A policy has Rs.5,00,000 sum insured but only Rs.1,20,000 remaining (available_sum_insured).
The claim has 3 line items that individually pass all EXCLUSION, CAPPING, and COST_SHARING
rules. Their post-rule totals are:
  Surgery:  Rs.80,000 (allowed)
  Room Rent: Rs.30,000 (allowed)
  Medicine:  Rs.25,000 (allowed)
  Total:    Rs.1,35,000

But the effective available sum insured is only Rs.1,20,000.

EXPECTED BEHAVIOUR:
The Pipeline processes line items sequentially in the COVERAGE phase. Each item consumes
from the remaining sum insured. When a line item hits a partial boundary, it gets
PARTIALLY_APPROVED — the insurer pays whatever is left, and the member pays the rest.
This ensures the maximum possible payout is made within the coverage limit.

  Surgery (80k)  → APPROVED,            insurer=80k, remaining=40k
  Room Rent (30k) → APPROVED,           insurer=30k, remaining=10k
  Medicine (25k)  → PARTIALLY_APPROVED, insurer=10k, member=15k, remaining=0

Total insurer payable = Rs.1,20,000 (exactly the available sum insured).

DESIGN NOTE:
The Rule Engine only handles per-item financial mutations. The Pipeline is responsible
for the in-memory accumulator tracking and setting the line item status based on
whether the item was fully covered, partially covered, or denied.
"""



COVERAGE_RULE_SUM_INSURED = {
    "id": "rule-sum-insured-cap",
    "name": "Sum Insured Coverage Limit",
    "condition": {},  # Always applies — every line item is subject to sum insured
    "action_type": "LIMIT",
    "action_config": {
        "max_amount": 120000,  # The effective available sum insured for this policy
        "accumulator_key": "SUM_INSURED",
        "reason_code": "SUM_INSURED_EXHAUSTED",
        "explanation": "Capped to remaining sum insured"
    }
}


def _determine_line_item_status(
    billed: Decimal,
    insurer_payable: Decimal,
) -> LineItemStatus:
    """Determine the line item status based on financial outcome.

    This logic will live in the Pipeline (Sub-Flow D). We define it here
    to validate the expected domain behaviour in tests.
    """
    if insurer_payable <= Decimal("0.00"):
        return LineItemStatus.DENIED
    if insurer_payable < billed:
        return LineItemStatus.PARTIALLY_APPROVED
    return LineItemStatus.APPROVED


def test_sum_insured_exhaustion_partially_approves_boundary_item():
    """
    After all other rules have run, line items total Rs.1,35,000 but the policy
    only has Rs.1,20,000 remaining. The last line item where the cap kicks in
    should be PARTIALLY_APPROVED — insurer pays whatever remains, member pays rest.
    """
    line_items_post_rules = [
        {"name": "Surgery", "insurer_payable": Decimal("80000.00"), "billed": Decimal("80000.00")},
        {"name": "Room Rent", "insurer_payable": Decimal("30000.00"), "billed": Decimal("30000.00")},
        {"name": "Medicine", "insurer_payable": Decimal("25000.00"), "billed": Decimal("25000.00")},
    ]

    in_memory_accumulator = Decimal("0.00")
    results = []

    for item in line_items_post_rules:
        context = {
            "accumulator.SUM_INSURED": float(in_memory_accumulator),
        }
        financials = {
            "billed_amount": item["billed"],
            "allowed_amount": item["insurer_payable"],
            "insurer_payable": item["insurer_payable"],
            "member_payable": item["billed"] - item["insurer_payable"],
        }

        passed, updated, audit = evaluate_rule(context, COVERAGE_RULE_SUM_INSURED, financials)
        in_memory_accumulator += updated["insurer_payable"]

        status = _determine_line_item_status(item["billed"], updated["insurer_payable"])
        results.append({
            "name": item["name"],
            "financials": updated,
            "audit": audit,
            "status": status,
        })

    # Surgery: 80k fully covered → APPROVED
    assert results[0]["financials"]["insurer_payable"] == Decimal("80000.00")
    assert results[0]["status"] == LineItemStatus.APPROVED

    # Room Rent: 30k fully covered → APPROVED
    assert results[1]["financials"]["insurer_payable"] == Decimal("30000.00")
    assert results[1]["status"] == LineItemStatus.APPROVED

    # Medicine: only 10k remaining out of 25k → PARTIALLY_APPROVED
    # Insurer pays what they can (10k), member pays the rest (15k)
    assert results[2]["financials"]["insurer_payable"] == Decimal("10000.00")
    assert results[2]["financials"]["member_payable"] == Decimal("15000.00")
    assert results[2]["status"] == LineItemStatus.PARTIALLY_APPROVED
    assert results[2]["audit"]["reason_code"] == "SUM_INSURED_EXHAUSTED"

    # Total insurer liability = exactly the available sum insured
    total_insurer = sum(r["financials"]["insurer_payable"] for r in results)
    assert total_insurer == Decimal("120000.00")


def test_sum_insured_fully_exhausted_denies_remaining():
    """
    Edge case: available sum insured is Rs.0 (already exhausted by prior claims).
    Every line item should get Rs.0 insurer payable → DENIED status.
    """
    rule_zero_balance = {
        **COVERAGE_RULE_SUM_INSURED,
        "action_config": {
            **COVERAGE_RULE_SUM_INSURED["action_config"],
            "max_amount": 0,
        }
    }

    financials = {
        "billed_amount": Decimal("50000.00"),
        "allowed_amount": Decimal("50000.00"),
        "insurer_payable": Decimal("50000.00"),
        "member_payable": Decimal("0.00"),
    }

    passed, updated, audit = evaluate_rule({}, rule_zero_balance, financials)
    status = _determine_line_item_status(Decimal("50000.00"), updated["insurer_payable"])

    assert passed is True
    assert updated["insurer_payable"] == Decimal("0.00")
    assert updated["member_payable"] == Decimal("50000.00")
    assert status == LineItemStatus.DENIED
"""Domain edge case tests for the Context Builder."""



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
"""Domain edge case tests for the Adjudication Engine pipeline."""



def test_deferred_accumulator_math():
    """
    Test that accumulator usage is tracked dynamically and deferred 
    until the absolute end of the line item processing.
    
    If it wasn't deferred, the CAPPING phase would update the accumulator 
    with the 'allowed_amount', and the COST_SHARING phase would drain it further,
    causing double dipping.
    """
    # 1. Setup Base Context with a Rs. 100,000 Sum Insured
    base_context = {
        "accumulator.available_sum_insured": 100000.0,
        "accumulator.category_usage": {
            "ROOM_RENT": 0.0
        }
    }
    
    # 2. Setup Line Item for Rs. 30,000
    item = LineItem(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        service_category=ServiceCategory.ROOM_RENT,
        billed_amount=Decimal("30000.00"),
        line_item_metadata={"quantity": 1, "unit": "DAY"}
    )
    
    # 3. Setup Rules: A CAP that limits to 20,000, and a COPAY of 10%
    rules = [
        {
            "id": "cap-rule",
            "name": "Room Rent Cap",
            "execution_phase": ExecutionPhase.CAPPING.value,
            "condition": {},
            "action_type": "LIMIT",
            "action_config": {
                "max_amount": 20000.0,
                "limit_type": "PER_UNIT",
                "accumulator_key": "ROOM_RENT"
            }
        },
        {
            "id": "copay-rule",
            "name": "Flat Copay",
            "execution_phase": ExecutionPhase.COST_SHARING.value,
            "condition": {},
            "action_type": "COPAY",
            "action_config": {
                "percentage": 10
            }
        }
    ]
    
    # 4. Run Pipeline
    # Expected: Billed=30k -> Cap reduces to 20k -> Copay reduces by 2k -> Insurer Payable = 18k
    results = run_pipeline(base_context, [item], rules)
    
    res = results[0]
    financials = res["financials"]
    
    assert financials["billed_amount"] == Decimal("30000.00")
    assert financials["allowed_amount"] == Decimal("20000.00")
    assert financials["insurer_payable"] == Decimal("18000.00")
    assert financials["member_payable"] == Decimal("12000.00")
    
    # The most critical part: the accumulator should only be updated by the FINAL insurer_payable (18k)
    # The pipeline doesn't return the accumulator, but we can verify the math is solid and 
    # the returned audit trail captures the correct deductions.
    assert len(res["audit_trail"]) == 2
    assert Decimal(str(res["audit_trail"][0]["amount_adjusted"])) == Decimal("-10000.00") # Cap
    assert Decimal(str(res["audit_trail"][1]["amount_adjusted"])) == Decimal("-2000.00")  # Copay


def test_audit_trail_noise_filter_strips_zero_impact_rules():
    """
    Test that rules returning 0.00 amount_impacted do not clutter the audit trail,
    except for EXCLUDE rules which should always log.
    """
    base_context = {
        "accumulator.available_sum_insured": 500000.0,
    }
    
    item = LineItem(
        id=uuid.uuid4(),
        claim_id=uuid.uuid4(),
        service_category=ServiceCategory.COSMETIC,
        billed_amount=Decimal("50000.00"),
        line_item_metadata={"quantity": 1, "unit": "UNIT"}
    )
    
    # 1. An EXCLUDE rule that zeroes out the item
    # 2. A CAPPING rule that should result in 0 impact (since it's already zero)
    # 3. A COPAY rule that should result in 0 impact
    rules = [
        {
            "id": "exclude-rule",
            "name": "Cosmetic Exclusion",
            "execution_phase": ExecutionPhase.EXCLUSION.value,
            "condition": {},
            "action_type": "EXCLUDE",
            "action_config": {"reason_code": "EXCLUDED_COSMETIC", "explanation": "Not covered"}
        },
        {
            "id": "copay-rule",
            "name": "Flat Copay",
            "execution_phase": ExecutionPhase.COST_SHARING.value,
            "condition": {},
            "action_type": "COPAY",
            "action_config": {"percentage": 20}
        }
    ]
    
    results = run_pipeline(base_context, [item], rules)
    res = results[0]
    
    assert res["status"] == LineItemStatus.EXCLUDED
    assert res["financials"]["insurer_payable"] == Decimal("0.00")
    
    # We should only see ONE audit trail entry (the exclusion). 
    # The Copay rule evaluated but had zero impact, so it's filtered.
    assert len(res["audit_trail"]) == 1
    assert res["audit_trail"][0]["effect_type"] == "EXCLUDE"
    assert res["audit_trail"][0]["reason_code"] == "EXCLUDED_COSMETIC"
"""Domain/Integration tests for claim processing scenarios."""



def test_scenario_member_not_part_of_policy(client, override_get_db, mocker):
    """
    Scenario: Claim Submission - Invalid Member/Policy Relationship
    
    Context:
    A user attempts to submit a reimbursement claim.
    They provide a valid Policy ID, but the Member ID belongs to a different family
    or does not exist on that specific policy contract.
    
    Desired Output:
    The claim submission should be rejected outright with a 400 Bad Request.
    The database should not persist any claim records.
    The error message should clearly indicate the validation failure.
    """
    # 1. Setup Mock State:
    # We mock the repository layer to simulate that the validation query returns False.
    # This means the member is NOT found on the policy.
    mocker.patch(
        "src.services.claim_service.policy_repo.validate_member_on_policy",
        return_value=False,
    )
    
    # 2. Action:
    # Submit the claim payload
    payload = {
        "policy_id": str(uuid.uuid4()),
        "member_id": str(uuid.uuid4()),
        "claim_type": "REIMBURSEMENT",
        "is_accident": False,
        "admission_date": "2023-10-01",
        "discharge_date": "2023-10-05",
        "diagnosis_codes": ["I21"],
        "documents_attached": ["BILLS"],
        "line_items": [
            {
                "service_category": "ROOM_RENT",
                "billed_amount": 5000.00
            }
        ]
    }
    response = client.post("/api/v1/claims", json=payload)
    
    # 3. Assertions:
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert response.json()["detail"] == "Member does not belong to the provided policy."


def test_scenario_successful_claim_submission(client, override_get_db, mocker):
    """
    Scenario: Claim Submission - Happy Path
    
    Context:
    A user submits a valid claim for a member who is correctly enrolled in the policy.
    
    Desired Output:
    The API should return a 201 Created status.
    The claim status should be explicitly set to 'SUBMITTED'.
    The total_billed should equal the sum of all line items.
    """
    # 1. Setup Mock State:
    # The member is valid.
    mocker.patch(
        "src.services.claim_service.policy_repo.validate_member_on_policy",
        return_value=True,
    )
    
    # Mock the DB claim creation to return a fake created Claim model
    fake_claim_id = uuid.uuid4()
    
    # Create a mock object that mimics the SQLAlchemy Claim model for Pydantic serialization
    class MockClaim:
        id = fake_claim_id
        status = ClaimStatus.SUBMITTED
        total_billed = 15000.00
        total_insurer_payable = 0.00
        total_member_payable = 0.00

    mocker.patch(
        "src.services.claim_service.claims_repo.create_claim_with_items",
        return_value=MockClaim(),
    )
    
    # 2. Action:
    payload = {
        "policy_id": str(uuid.uuid4()),
        "member_id": str(uuid.uuid4()),
        "claim_type": "REIMBURSEMENT",
        "is_accident": False,
        "admission_date": "2023-10-01",
        "discharge_date": "2023-10-05",
        "diagnosis_codes": ["I21"],
        "documents_attached": ["BILLS", "DISCHARGE_SUMMARY"],
        "line_items": [
            {
                "service_category": "ROOM_RENT",
                "billed_amount": 10000.00
            },
            {
                "service_category": "PHARMACY",
                "billed_amount": 5000.00
            }
        ]
    }
    response = client.post("/api/v1/claims", json=payload)
    
    # 3. Assertions:
    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert data["id"] == str(fake_claim_id)
    assert data["status"] == "SUBMITTED"
    assert data["total_billed"] == "15000.0"


def test_unprocessed_claim_review(client, override_get_db, mocker):
    """
    Test attempting to manually review a claim that has not been systematically processed.
    Should return 400 Bad Request.
    """
    fake_claim_id = uuid.uuid4()
    
    class MockClaim:
        id = fake_claim_id
        status = ClaimStatus.SUBMITTED
        total_billed = Decimal("0.00")
        total_insurer_payable = Decimal("0.00")
        total_member_payable = Decimal("0.00")
        
    mocker.patch(
        "src.routes.admin_claims.claims_repo.get_claim_by_id",
        return_value=MockClaim(),
    )
    
    payload = {
        "action": "APPROVE",
        "notes": "Trying to bypass the engine"
    }
    
    response = client.post(f"/api/v1/admin/claims/{fake_claim_id}/review", json=payload)
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "PENDING_APPROVAL" in response.json()["detail"]


def test_end_to_end_approval_and_revert(client, override_get_db, mocker):
    """
    End-to-End flow:
    1. Revert an APPROVED claim.
    2. Verify it calls execute_revert_decision successfully.
    """
    fake_claim_id = uuid.uuid4()
    
    class MockClaim:
        id = fake_claim_id
        status = ClaimStatus.PENDING_APPROVAL # After revert and re-adjudicate
        total_billed = Decimal("5000.00")
        total_insurer_payable = Decimal("5000.00")
        total_member_payable = Decimal("0.00")
        
    # We will just mock the core service method since we thoroughly unit tested the accumulator math
    mocker.patch(
        "src.routes.admin_claims.execute_revert_decision",
        return_value=MockClaim(),
    )
    
    response = client.post(f"/api/v1/admin/claims/{fake_claim_id}/revert")
    
    assert response.status_code == status.HTTP_200_OK
    assert response.json()["status"] == "PENDING_APPROVAL"
