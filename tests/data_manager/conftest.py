"""
Shared fixtures for DataManager tests

Provides fixtures for:
- DataManagerCodeAgent instances
- Test database sessions
- Mock configurations
- Test data
"""
import os
import sys
import pytest
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.base import SessionLocal, Base, engine
from backend.database.models import Patient, Conversation, Message
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.agents.data_manager import DataManagerCodeAgent, is_request_blocked
from backend.config.config_manager import get_config, reset_config
from backend.services.sandbox_session import SandboxSession


# ============================================
# Configuration Fixtures
# ============================================

@pytest.fixture
def mock_openai_model():
    """
    Mock OpenAIModel for testing without real API calls

    Patches OpenAIModel to avoid making real LLM API calls during tests.
    """
    with patch("backend.agents.data_manager.OpenAIModel") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


@pytest.fixture
def mock_code_agent():
    """
    Mock ToolCallingAgent for testing

    Patches ToolCallingAgent to test agent logic without running the full agent.
    """
    with patch("backend.agents.data_manager.ToolCallingAgent") as mock:
        mock_instance = MagicMock()
        mock.return_value = mock_instance
        yield mock


# ============================================
# Agent Fixtures
# ============================================

@pytest.fixture
def data_manager(mock_openai_model, mock_code_agent):
    """
    Create a DataManagerCodeAgent instance with mocked dependencies

    This fixture provides a data manager agent that won't make real API calls.
    Uses the default config.yaml from the project root.
    """
    reset_config()
    # Don't pass config_path - will use default config.yaml
    agent = DataManagerCodeAgent()
    yield agent
    reset_config()


@pytest.fixture
def data_manager_with_real_code():
    """
    Create a DataManagerCodeAgent with real ToolCallingAgent but mocked model

    This allows testing the actual tool calling logic without making
    real LLM API calls.
    Uses the default config.yaml from the project root.
    """
    reset_config()
    with patch("backend.agents.data_manager.OpenAIModel") as mock_model:
        mock_model_instance = MagicMock()
        mock_model.return_value = mock_model_instance
        # Don't pass config_path - will use default config.yaml
        agent = DataManagerCodeAgent()
        yield agent
    reset_config()


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture(scope="function")
def db_session():
    """
    Function-scoped database session

    Each test gets a clean session with automatic rollback.
    """
    # Create all tables
    Base.metadata.create_all(bind=engine)

    # Create session
    session = SessionLocal()

    # Begin transaction for rollback
    session.begin()

    yield session

    # Cleanup
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def clean_db(db_session):
    """
    Clean database with test data

    Deletes all existing data and provides a clean database.
    Note: This can cause SQLite locks in concurrent tests.
    Uses try/except to handle database lock errors gracefully.
    """
    # Try to clean up existing data
    try:
        # Close any existing transactions
        db_session.rollback()

        # Delete data in specific order to handle foreign keys
        db_session.query(Message).delete(synchronize_session=False)
        db_session.query(Conversation).delete(synchronize_session=False)
        db_session.query(Patient).delete(synchronize_session=False)
        db_session.commit()
    except Exception as e:
        # If cleanup fails due to lock, just rollback and continue
        # The test will still work with the existing data
        db_session.rollback()

    yield db_session


# ============================================
# Test Data Fixtures
# ============================================

@pytest.fixture
def sample_patient_data():
    """Sample patient creation data"""
    return PatientCreate(
        name="Test Patient",
        age=30,
        gender="male",
        phone="13800000000",
        address="Test Address"
    )


@pytest.fixture
def test_patient(clean_db, sample_patient_data):
    """Create a test patient in the database"""
    patient = patient_crud.create(clean_db, sample_patient_data)
    clean_db.commit()
    yield patient


@pytest.fixture
def multiple_test_patients(clean_db):
    """Create multiple test patients for testing"""
    patients = []
    for i in range(3):
        patient = patient_crud.create(clean_db, PatientCreate(
            name=f"Patient {i}",
            age=25 + i * 5,
            gender="male" if i % 2 == 0 else "female"
        ))
        patients.append(patient)

    clean_db.commit()
    yield patients


# ============================================
# Sandbox Fixtures
# ============================================

@pytest.fixture
def sandbox_session(clean_db):
    """
    Create a sandbox session for testing

    Provides a SandboxSession wrapper around a real database session.
    """
    conversation_id = "test_conversation_123"
    sandbox = SandboxSession(clean_db, conversation_id)
    yield sandbox
    sandbox.close()


# ============================================
# Helper Functions
# ============================================

class DataManagerTestHelpers:
    """Helper methods for DataManager tests"""

    @staticmethod
    def assert_blocked_error(result: dict, table_name: str):
        """
        Assert that a result contains a blocked table error

        Args:
            result: Result dictionary from agent
            table_name: Expected blocked table name
        """
        assert result["success"] is False
        assert "error" in result
        assert table_name.lower() in result["error"].lower()

    @staticmethod
    def assert_success_result(result: dict, has_output: bool = True):
        """
        Assert that a result is successful

        Args:
            result: Result dictionary from agent
            has_output: Whether the result should have output
        """
        assert result["success"] is True
        assert "final_answer" in result
        if has_output:
            assert len(result["final_answer"]) > 0

    @staticmethod
    def create_patient_request(patient_id: str = None, name: str = "John Doe", age: int = 35) -> str:
        """
        Create a patient creation request string

        Args:
            patient_id: Optional patient ID
            name: Patient name
            age: Patient age

        Returns:
            Request string
        """
        return f"Create a new patient named '{name}', age {age}, gender male"

    @staticmethod
    def query_patient_request(patient_id: str) -> str:
        """
        Create a patient query request string

        Args:
            patient_id: Patient ID to query

        Returns:
            Request string
        """
        return f"Get the patient with ID {patient_id} and show their information"

    @staticmethod
    def update_patient_request(patient_id: str, field: str, value: str) -> str:
        """
        Create a patient update request string

        Args:
            patient_id: Patient ID to update
            field: Field to update
            value: New value

        Returns:
            Request string
        """
        return f"Update patient {patient_id}: set {field} to {value}"


@pytest.fixture
def test_helpers():
    """Provide test helper class"""
    return DataManagerTestHelpers


# ============================================
# Pytest Configuration
# ============================================

def pytest_configure(config):
    """Configure pytest markers for data manager tests"""
    config.addinivalue_line(
        "markers", "unit: Unit tests (no external dependencies)"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests (requires database)"
    )
    config.addinivalue_line(
        "markers", "slow: Slow-running tests (real API calls)"
    )
    config.addinivalue_line(
        "markers", "sandbox: Tests for sandbox mechanism"
    )
    config.addinivalue_line(
        "markers", "security: Tests for security blocking"
    )
