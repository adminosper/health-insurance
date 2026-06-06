import pytest
from fastapi.testclient import TestClient
from main import app
import uuid
from src.shared.enums import ClaimStatus

client = TestClient(app)

def test():
    fake_claim_id = uuid.uuid4()
    response = client.post(f"/api/v1/admin/claims/{fake_claim_id}/revert")
    print("STATUS", response.status_code)
    print("JSON", response.json())

test()
