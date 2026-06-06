import pytest
from fastapi.testclient import TestClient

from main import app
from src.database.connection import get_db

@pytest.fixture
def client():
    """Provides a FastAPI test client."""
    return TestClient(app)

@pytest.fixture
def mock_db_session(mocker):
    """Provides a mocked SQLAlchemy DB session."""
    session_mock = mocker.MagicMock()
    return session_mock

@pytest.fixture
def override_get_db(mock_db_session):
    """Overrides the FastAPI get_db dependency to use the mocked session."""
    def _override_get_db():
        yield mock_db_session
        
    app.dependency_overrides[get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
