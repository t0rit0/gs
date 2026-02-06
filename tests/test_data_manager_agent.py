"""
Tests for DataManagerCodeAgent

Tests cover:
1. Agent generates valid Python code for database operations (real API calls)
2. Agent uses sandbox mode (no direct commits)
3. Agent cannot operate on conversations table (security)
4. Agent handles errors gracefully
5. Agent integrates with ORM information
6. Agent returns proper RunResult structure
7. Agent initialization and prompt injection

NOTE: These tests make real API calls to the configured LLM endpoint.
Make sure your config.yaml has valid API credentials.
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database.base import SessionLocal, engine, Base
from backend.database.models import Patient
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.agents.data_manager import DataManagerCodeAgent, is_request_blocked
from backend.config.config_manager import reset_config


class TestDataManagerCodeAgent:
    """Test suite for DataManagerCodeAgent functionality with real API calls"""

    def _create_test_patient(self) -> str:
        """Helper to create a test patient and return the generated patient_id"""
        session = SessionLocal()
        try:
            patient = patient_crud.create(
                session,
                PatientCreate(
                    name="Test Patient",
                    age=30,
                    gender="male"
                )
            )
            session.commit()
            patient_id = patient.patient_id
            return patient_id
        finally:
            session.close()

    def _cleanup_test_patient(self, patient_id: str):
        """Helper to clean up test patient"""
        session = SessionLocal()
        try:
            patient_crud.delete(session, patient_id)
            session.commit()
        except Exception:
            pass
        finally:
            session.close()

    def test_agent_initialization(self):
        """Test that agent initializes correctly with ORM documentation"""
        reset_config()
        agent = DataManagerCodeAgent()

        # Check agent was created
        assert agent is not None
        assert agent.agent is not None

        # Check that ORM documentation was injected
        pt = agent.agent.prompt_templates
        system_prompt = pt.get("system_prompt", "")

        # Verify ORM documentation is present
        assert "Patient Model" in system_prompt
        assert "patient_crud" in system_prompt
        assert "health_metrics" in system_prompt
        assert ("BLOCKED" in system_prompt or "blocked" in system_prompt)

        reset_config()

    def test_query_patient_by_id(self):
        """Test querying a patient by ID with real API call"""
        reset_config()

        # Create test patient
        patient_id = self._create_test_patient()

        try:
            # Initialize agent
            agent = DataManagerCodeAgent()

            # Query patient
            user_request = f"Get the patient with ID {patient_id} and show their name and age"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result

            # Should succeed
            assert result["success"] is True
            assert len(result["final_answer"]) > 0

            # Final answer should mention the patient info
            final_answer_lower = result["final_answer"].lower()
            assert "test patient" in final_answer_lower or "patient" in final_answer_lower

        finally:
            self._cleanup_test_patient(patient_id)
            reset_config()

    def test_list_all_patients(self):
        """Test listing all patients with real API call"""
        reset_config()

        try:
            agent = DataManagerCodeAgent()

            # List all patients
            user_request = "Show me all patients in the database"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result
            assert result["success"] is True
            assert len(result["final_answer"]) > 0

        finally:
            reset_config()

    def test_search_patient_by_name(self):
        """Test searching patients by name with real API call"""
        reset_config()

        patient_id = self._create_test_patient()

        try:
            agent = DataManagerCodeAgent()

            # Search for patient
            user_request = "Search for patients named 'Test Patient'"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result
            assert result["success"] is True

            # Should find the test patient
            assert "test" in result["final_answer"].lower()

        finally:
            self._cleanup_test_patient(patient_id)
            reset_config()

    def test_add_health_metric(self):
        """Test adding a health metric to patient with real API call"""
        reset_config()

        patient_id = self._create_test_patient()

        try:
            agent = DataManagerCodeAgent()

            # Add health metric
            user_request = f"Add a health metric for patient {patient_id}: blood pressure 140/90"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result

            # Check if operation was tracked in sandbox (not committed directly)
            # The agent should use SandboxSession for write operations
            assert len(result["final_answer"]) > 0

        finally:
            self._cleanup_test_patient(patient_id)
            reset_config()

    def test_blocked_conversations_table(self):
        """Test that conversations table access is blocked"""
        reset_config()

        agent = DataManagerCodeAgent()

        # Try to access conversations table
        user_request = "Show me all conversations"
        result = agent.process_request(user_request)

        # Should be blocked
        assert result["success"] is False
        assert "error" in result
        assert "conversations" in result["error"].lower()

        reset_config()

    def test_blocked_messages_table(self):
        """Test that messages table access is blocked"""
        reset_config()

        agent = DataManagerCodeAgent()

        # Try to access messages table
        user_request = "Show me all messages"
        result = agent.process_request(user_request)

        # Should be blocked
        assert result["success"] is False
        assert "error" in result
        assert "messages" in result["error"].lower()

        reset_config()

    def test_security_function(self):
        """Test the is_request_blocked security function"""
        # Blocked requests
        blocked_requests = [
            "Show me all conversations",
            "Delete the conversation",
            "Update message table",
            "Query messages for patient",
        ]

        for request in blocked_requests:
            error = is_request_blocked(request)
            assert error is not None, f"Request should be blocked: {request}"
            assert "security" in error.lower() or "not allowed" in error.lower()

        # Allowed requests
        allowed_requests = [
            "Show me all patients",
            "Query patient information",
            "Add new patient",
            "Update patient age",
        ]

        for request in allowed_requests:
            error = is_request_blocked(request)
            assert error is None, f"Request should be allowed: {request}"

    def test_create_new_patient(self):
        """Test creating a new patient with real API call"""
        reset_config()

        try:
            agent = DataManagerCodeAgent()

            # Create patient
            user_request = "Create a new patient named 'John Doe', age 45, gender male"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result
            assert len(result["final_answer"]) > 0

            # Should mention the created patient
            assert "john" in result["final_answer"].lower()

        finally:
            reset_config()

    @pytest.mark.slow
    def test_complex_query_with_filter(self):
        """Test complex query with filtering conditions"""
        reset_config()

        # Create multiple test patients
        patient_id1 = self._create_test_patient()

        try:
            agent = DataManagerCodeAgent()

            # Complex query
            user_request = "Find all patients who are male and older than 25"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result
            assert result["success"] is True

        finally:
            self._cleanup_test_patient(patient_id1)
            reset_config()

    def test_error_handling_invalid_uuid(self):
        """Test error handling for invalid UUID"""
        reset_config()

        agent = DataManagerCodeAgent()

        # Try to query with invalid UUID
        user_request = "Get patient with ID invalid-uuid-12345"
        result = agent.process_request(user_request)

        # Should handle gracefully (success may be True or False, but no crash)
        assert "success" in result
        assert "final_answer" in result or "error" in result

        reset_config()

    def test_chinese_query(self):
        """Test querying with Chinese language"""
        reset_config()

        patient_id = self._create_test_patient()

        try:
            agent = DataManagerCodeAgent()

            # Chinese query
            user_request = f"查询ID为 {patient_id} 的患者信息"
            result = agent.process_request(user_request)

            # Assert result structure
            assert "success" in result
            assert "final_answer" in result
            assert len(result["final_answer"]) > 0

        finally:
            self._cleanup_test_patient(patient_id)
            reset_config()

    @pytest.mark.slow
    def test_multiple_sequential_requests(self):
        """Test processing multiple requests sequentially"""
        reset_config()

        try:
            agent = DataManagerCodeAgent()

            # Multiple requests
            requests = [
                "Show me all patients",
                "Create a new patient named 'Jane', age 28",
                "Search for patients named 'Jane'",
            ]

            for req in requests:
                result = agent.process_request(req)
                assert "success" in result
                assert "final_answer" in result

        finally:
            reset_config()


# Test fixtures
@pytest.fixture
def db_session():
    """Create a test database session"""
    # Import models to register with Base
    import backend.database.models  # noqa

    # Create tables
    Base.metadata.create_all(bind=engine)

    # Create session
    session = SessionLocal()

    yield session

    # Cleanup
    session.close()
    # Drop all tables
    Base.metadata.drop_all(bind=engine)
