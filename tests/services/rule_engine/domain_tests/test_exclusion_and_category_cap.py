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

from decimal import Decimal
from src.services.rule_engine.engine import evaluate_rule


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
