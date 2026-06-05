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

from decimal import Decimal
from src.services.rule_engine.engine import evaluate_rule
from src.shared.enums import LineItemStatus


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
