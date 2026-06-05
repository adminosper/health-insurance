"""Pre-adjudication deterministic validation checks."""

from typing import Tuple

from src.models.claims import Claim
from src.models.policies import Policy


def run_pre_adjudication_checks(claim: Claim, policy: Policy) -> Tuple[bool, str]:
    """Execute hard-coded validations before the rule engine runs.
    
    Returns:
        A tuple of (is_valid, error_reason). If is_valid is False, the claim 
        should immediately transition to REJECTED.
    """
    if claim.total_billed <= 0:
        return False, "Total billed amount must be greater than zero."

    if claim.admission_date < policy.tenure_start or claim.admission_date > policy.tenure_end:
        return False, "Admission date is outside the policy active tenure."

    # Could add more checks here (e.g., waiting period for accidental claims, 
    # checking if member is actually enrolled on policy, etc. if not done at submission)

    return True, ""
