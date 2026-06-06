"""Accumulator Manager for managing the state of policy limits and usages."""

from decimal import Decimal
from typing import List

from src.models.claims import Claim, LineItem
from src.models.policies import Accumulator
from src.shared.enums import ActionType, LineItemStatus


def apply_claim_to_accumulator(accumulator: Accumulator, claim: Claim, line_items: List[LineItem]) -> None:
    """
    Physically debit the accumulator based on an approved claim's financials.
    
    This function modifies the accumulator object in place. The caller is responsible 
    for committing the database transaction.
    """
    accumulator.available_sum_insured -= claim.total_insurer_payable
    
    for item in line_items:
        if item.status in (LineItemStatus.APPROVED, LineItemStatus.PARTIALLY_APPROVED):
            # Update category usage
            cat = item.service_category.value
            current_usage = Decimal(str(accumulator.category_usage.get(cat, 0)))
            accumulator.category_usage[cat] = float(current_usage + item.insurer_payable)
            
            # Check for DEDUCTIBLE in audit trail
            for audit in item.audit_trail:
                if audit.get("effect_type") == ActionType.DEDUCTIBLE.value:
                    deductible_amount = abs(Decimal(str(audit.get("amount_adjusted", 0))))
                    accumulator.active_deductible_paid += deductible_amount


def revert_claim_from_accumulator(accumulator: Accumulator, claim: Claim, line_items: List[LineItem]) -> None:
    """
    Reverse the physical debits on the accumulator that were made by a previously approved claim.
    
    This function modifies the accumulator object in place to cleanly untangle
    the financial state. The caller is responsible for committing the transaction.
    """
    accumulator.available_sum_insured += claim.total_insurer_payable
    
    for item in line_items:
        if item.status in (LineItemStatus.APPROVED, LineItemStatus.PARTIALLY_APPROVED):
            # Revert category usage
            cat = item.service_category.value
            current_usage = Decimal(str(accumulator.category_usage.get(cat, 0)))
            accumulator.category_usage[cat] = float(max(Decimal("0.00"), current_usage - item.insurer_payable))
            
            # Revert deductible
            for audit in item.audit_trail:
                if audit.get("effect_type") == ActionType.DEDUCTIBLE.value:
                    deductible_amount = abs(Decimal(str(audit.get("amount_adjusted", 0))))
                    accumulator.active_deductible_paid = max(Decimal("0.00"), accumulator.active_deductible_paid - deductible_amount)
