import uuid
from decimal import Decimal
from unittest.mock import MagicMock

from src.models.claims import ClaimStatus
from src.serializers.audit import AuditTrailEntry
from src.services.claim_service import generate_eob
from src.shared.enums import ActionType, ExecutionPhase, ServiceCategory


def test_generate_eob_not_found(mocker):
    db = MagicMock()
    mocker.patch("src.services.claim_service.claims_repo.get_claim_by_id", return_value=None)
    assert generate_eob(db, uuid.uuid4()) is None


def test_generate_eob_success(mocker):
    db = MagicMock()
    
    mock_claim = MagicMock()
    mock_claim.id = uuid.uuid4()
    mock_claim.status = ClaimStatus.PENDING_APPROVAL
    mock_claim.total_billed = Decimal("12000.00")
    mock_claim.total_insurer_payable = Decimal("9000.00")
    mock_claim.total_member_payable = Decimal("3000.00")
    
    mocker.patch("src.services.claim_service.claims_repo.get_claim_by_id", return_value=mock_claim)
    
    mock_line_item = MagicMock()
    mock_line_item.service_category = ServiceCategory.ROOM_RENT
    mock_line_item.billed_amount = Decimal("12000.00")
    mock_line_item.allowed_amount = Decimal("10000.00")
    mock_line_item.insurer_payable = Decimal("9000.00")
    mock_line_item.status = "APPROVED"
    mock_line_item.audit_trail = [
        AuditTrailEntry(
            step=1,
            rule_name="Room Rent Cap",
            stage=ExecutionPhase.CAPPING,
            effect_type=ActionType.LIMIT,
            amount_before=Decimal("12000.00"),
            amount_adjusted=Decimal("-2000.00"),
            amount_after=Decimal("10000.00"),
            reason_code="LIMIT_EXCEEDED",
            explanation="Capped at 10k"
        ).model_dump(mode="json")
    ]
    
    mocker.patch("src.services.claim_service.claims_repo.get_line_items_by_claim_id", return_value=[mock_line_item])
    
    eob = generate_eob(db, mock_claim.id)
    
    assert eob is not None
    assert eob.claim_id == mock_claim.id
    assert len(eob.line_items) == 1
    assert eob.line_items[0].member_payable == Decimal("3000.00")
    assert len(eob.line_items[0].adjustments) == 1
    assert eob.line_items[0].adjustments[0].effect_type == ActionType.LIMIT

