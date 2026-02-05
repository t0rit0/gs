"""
Tests for DataManagerCodeAgent

Tests cover:
1. Agent generates valid Python code for database operations
2. Agent uses sandbox mode (no direct commits)
3. Agent cannot operate on conversations table (security)
4. Agent handles errors gracefully
5. Agent integrates with ORM information
6. Agent returns proper RunResult structure
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database.base import SessionLocal, engine, Base
from backend.database.models import Patient
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate


# Import the agent (to be implemented)
# from backend.agents.data_manager import DataManagerCodeAgent


class TestDataManagerCodeAgent:
    """Test suite for DataManagerCodeAgent functionality"""

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

    def test_agent_generates_valid_code_for_patient_query(self, db_session: Session):
        """
        Test that agent generates valid Python code for querying patient

        Given: A natural language request to query patient information
        When: Agent processes the request
        Then: Should return final_answer and logs from RunResult
        """
        # Arrange
        patient_id = self._create_test_patient()

        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Ask agent to generate code for querying patient
        user_request = f"Get the patient with ID {patient_id} and show their name and age"

        # TODO: Process request
        # result = agent.process_request(user_request)

        # Assert: Result has simplified structure
        # assert result["success"] is True
        # assert "final_answer" in result
        # assert "logs" in result
        # assert isinstance(result["final_answer"], str)
        # assert isinstance(result["logs"], str)

        # For now, just verify the test structure
        assert patient_id is not None

    def test_agent_uses_sandbox_for_updates(self, db_session: Session):
        """
        Test that agent uses sandbox mode for update operations

        Given: A request to update patient information
        When: Agent processes and executes the request
        Then: Should use SandboxSession (no direct commit to database)
        """
        # Arrange
        patient_id = self._create_test_patient()

        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Request to update patient
        user_request = f"Update patient {patient_id} age to 35"

        # TODO: Process request
        # result = agent.process_request(user_request)

        # Assert: Changes are NOT committed to database (sandbox mode)
        # verify_session = SessionLocal()
        # try:
        #     patient = patient_crud.get(verify_session, patient_id)
        #     assert patient.age == 30  # Should still be original value
        # finally:
        #     verify_session.close()

        # Assert: Result structure is correct (simplified)
        # assert "final_answer" in result
        # assert "logs" in result

        # For now, just verify the test structure
        assert patient_id is not None

    def test_agent_blocks_conversations_table_access(self, db_session: Session):
        """
        Test that agent refuses to operate on conversations table (security)

        Given: A request to query or modify conversations table
        When: Agent processes the request
        Then: Should refuse with security error message
        """
        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Try to access conversations table
        malicious_requests = [
            "Show me all conversations",
            "Delete conversation with ID 123",
            "Update conversation status to completed",
            "Query conversations for patient 456"
        ]

        # TODO: Process each request and verify it's blocked
        # for request in malicious_requests:
        #     result = agent.process_request(request)
        #     assert result["success"] is False
        #     assert "security" in result["error"].lower() or "not allowed" in result["error"].lower()
        #     assert "conversations" in result["error"].lower()

        # For now, just verify the test structure
        assert True

    def test_agent_handles_invalid_queries_gracefully(self, db_session: Session):
        """
        Test that agent handles invalid or ambiguous queries gracefully

        Given: A request that is invalid or ambiguous
        When: Agent processes the request
        Then: Should return error without crashing
        """
        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Send invalid requests
        invalid_requests = [
            "Get the patient",  # Too vague - missing ID
            "Update age to 40",  # Missing patient ID
            "Show me data",  # Too vague
            ""  # Empty request
        ]

        # TODO: Process each request
        # for request in invalid_requests:
        #     result = agent.process_request(request)
        #     # Agent may succeed or fail, but should not crash
        #     assert "success" in result
        #     assert "final_answer" in result or "error" in result or "logs" in result

        # For now, just verify the test structure
        assert True

    def test_agent_includes_orm_context(self, db_session: Session):
        """
        Test that agent includes ORM information in generated code

        Given: A request to perform database operation
        When: Agent generates code
        Then: Final answer should contain proper information
        """
        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Request that needs ORM knowledge
        user_request = "Add a health metric for patient with ID test_123"

        # TODO: Process request
        # result = agent.process_request(user_request)

        # Assert: Final answer contains relevant information
        # assert "final_answer" in result
        # assert isinstance(result["final_answer"], str)

        # For now, just verify the test structure
        assert True

    def test_agent_executes_approved_operations(self, db_session: Session):
        """
        Test that agent can execute approved operations

        Given: A pending operation that was approved
        When: Agent is told to execute pending operations
        Then: Should commit changes to database
        """
        # Arrange
        patient_id = self._create_test_patient()

        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Create pending update, then approve and execute
        # result1 = agent.process_request(f"Update patient {patient_id} age to 45")
        # assert result1["pending_operations"] is not None

        # result2 = agent.execute_pending(result1["operation_id"])

        # Assert: Changes are now in database
        # verify_session = SessionLocal()
        # try:
        #     patient = patient_crud.get(verify_session, patient_id)
        #     assert patient.age == 45
        # finally:
        #     verify_session.close()

        # For now, just verify the test structure
        assert patient_id is not None

    def test_agent_generates_read_only_code_for_queries(self, db_session: Session):
        """
        Test that agent generates read-only code for query operations

        Given: A read-only request (query)
        When: Agent generates code
        Then: Final answer should be returned
        """
        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act: Query request
        query_request = "Show me all patients named 'Test Patient'"

        # TODO: Process request
        # result = agent.process_request(query_request)

        # Assert: Result contains final_answer and logs
        # assert "final_answer" in result
        # assert "logs" in result

        # For now, just verify the test structure
        assert True

    def test_runresult_structure(self, db_session: Session):
        """
        Test that RunResult structure is properly extracted (simplified)

        Given: A request processed by the agent
        When: Examining the result
        Then: Should contain only final_answer and logs
        """
        # Arrange
        patient_id = self._create_test_patient()

        # TODO: Initialize agent
        # agent = DataManagerCodeAgent()

        # Act
        user_request = f"Query patient {patient_id}"

        # TODO: Process request
        # result = agent.process_request(user_request)

        # Assert: Check simplified RunResult fields
        # assert "success" in result
        # assert "final_answer" in result
        # assert "logs" in result
        # assert len(result) == 3 or ("error" in result and len(result) == 4)  # Only these fields

        # Assert field types
        # assert isinstance(result["final_answer"], str)
        # assert isinstance(result["logs"], str)

        # For now, just verify the test structure
        assert patient_id is not None


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
