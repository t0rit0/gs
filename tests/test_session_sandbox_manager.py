"""
Tests for Session-Level Sandbox Manager

This module tests the session-level sandbox management that allows
operations to be accumulated across multiple requests and approved
in a single batch at conversation end.

Test Coverage:
1. SandboxSessionManager - Manages sandboxes across multiple conversations
2. Cross-request operation accumulation
3. Batch approval at conversation end
4. Sandbox lifecycle management
5. Error handling and edge cases
"""

import pytest
from datetime import datetime
from sqlalchemy.orm import Session

from backend.database.base import SessionLocal, engine, Base
from backend.services.sandbox_session import SandboxSession, DatabaseOperation
from backend.database.models import Patient
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate


# ============================================
# Test: SandboxSessionManager
# ============================================

class TestSandboxSessionManagerBasics:
    """Test suite for basic SandboxSessionManager functionality"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_manager_initialization(self):
        """
        Test that SandboxSessionManager initializes correctly

        Given: A new SandboxSessionManager
        When: Initializing
        Then: Should have empty sessions dict and default configuration
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()

        assert manager.sessions == {}
        assert isinstance(manager.sessions, dict)

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_get_or_create_sandbox_creates_new(self):
        """
        Test that get_or_create_sandbox creates new sandbox

        Given: A SandboxSessionManager
        When: Calling get_or_create_sandbox for first time
        Then: Should create new SandboxSession
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        sandbox = manager.get_or_create_sandbox(real_session, "conv_123")

        assert sandbox is not None
        assert isinstance(sandbox, SandboxSession)
        assert sandbox.conversation_id == "conv_123"
        assert sandbox.is_sandboxed is True

        # Verify it's stored in manager
        assert "conv_123" in manager.sessions
        assert manager.sessions["conv_123"] is sandbox

        sandbox.close()
        real_session.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_get_or_create_sandbox_returns_existing(self):
        """
        Test that get_or_create_sandbox returns existing sandbox

        Given: A SandboxSessionManager with existing sandbox
        When: Calling get_or_create_sandbox again
        Then: Should return the same sandbox instance
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        # Create first sandbox
        sandbox1 = manager.get_or_create_sandbox(real_session, "conv_456")

        # Get same sandbox again
        sandbox2 = manager.get_or_create_sandbox(real_session, "conv_456")

        assert sandbox1 is sandbox2  # Same instance
        assert id(sandbox1) == id(sandbox2)

        sandbox1.close()
        real_session.close()


class TestCrossRequestOperationAccumulation:
    """Test suite for operation accumulation across multiple requests"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_operations_accumulate_across_requests(self, clean_db):
        """
        Test that operations from multiple requests accumulate

        Given: A SandboxSessionManager
        When: Making multiple requests with write operations
        Then: All operations should accumulate in the same sandbox
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        conversation_id = "conv_accumulate_test"

        # Request 1: Create first patient
        sandbox1 = manager.get_or_create_sandbox(clean_db, conversation_id)
        patient1 = Patient(
            patient_id="accum-1",
            name="Patient One",
            age=30,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox1.add(patient1)
        sandbox1.commit()

        operations_after_req1 = len(sandbox1.get_pending_operations())
        assert operations_after_req1 == 1

        # Request 2: Create second patient (same conversation)
        sandbox2 = manager.get_or_create_sandbox(clean_db, conversation_id)
        patient2 = Patient(
            patient_id="accum-2",
            name="Patient Two",
            age=35,
            gender="female",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox2.add(patient2)
        sandbox2.commit()

        # Both operations should be accumulated
        operations_after_req2 = len(sandbox2.get_pending_operations())
        assert operations_after_req2 == 2

        # Verify same sandbox instance
        assert sandbox1 is sandbox2

        # Verify none committed to database yet (use fresh session)
        verify_session = SessionLocal()
        try:
            check1 = verify_session.query(Patient).filter_by(patient_id="accum-1").first()
            check2 = verify_session.query(Patient).filter_by(patient_id="accum-2").first()
            assert check1 is None
            assert check2 is None
        finally:
            verify_session.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_update_and_create_accumulate(self, clean_db, test_patient):
        """
        Test that both updates and creates accumulate

        Given: An existing patient
        When: Creating new patient and updating existing one
        Then: Both operations should accumulate
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        conversation_id = "conv_update_create_test"

        # Request 1: Update existing patient
        sandbox1 = manager.get_or_create_sandbox(clean_db, conversation_id)
        patient = clean_db.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
        patient.age = 99
        sandbox1.commit()

        # Request 2: Create new patient
        sandbox2 = manager.get_or_create_sandbox(clean_db, conversation_id)
        new_patient = Patient(
            patient_id="update-create-new",
            name="New Patient",
            age=25,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox2.add(new_patient)
        sandbox2.commit()

        # Both operations accumulated
        operations = sandbox2.get_pending_operations()
        assert len(operations) == 2

        # Verify not committed yet (use fresh session)
        verify_session = SessionLocal()
        try:
            verify_patient = verify_session.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
            assert verify_patient.age != 99  # Not updated

            verify_new = verify_session.query(Patient).filter_by(patient_id="update-create-new").first()
            assert verify_new is None  # Not created
        finally:
            verify_session.close()


class TestBatchApprovalAtConversationEnd:
    """Test suite for batch approval workflow"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_approve_and_execute_all_operations(self, clean_db):
        """
        Test approving and executing all accumulated operations

        Given: A conversation with multiple pending operations
        When: Calling approve_and_execute_all
        Then: All operations should be committed to database
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        conversation_id = "conv_approve_test"

        # Accumulate multiple operations
        sandbox = manager.get_or_create_sandbox(clean_db, conversation_id)

        for i in range(3):
            patient = Patient(
                patient_id=f"approve-{i}",
                name=f"Approve Test {i}",
                age=30 + i,
                gender="male",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            sandbox.add(patient)
            sandbox.commit()

        # Verify pending operations
        assert len(sandbox.get_pending_operations()) == 3

        # Approve and execute all
        result = manager.approve_and_execute_all(clean_db, conversation_id)

        assert result["success"] is True
        assert result["executed_count"] == 3

        # Verify all committed to database
        for i in range(3):
            patient = clean_db.query(Patient).filter_by(patient_id=f"approve-{i}").first()
            assert patient is not None
            assert patient.name == f"Approve Test {i}"

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_approve_returns_operation_summary(self, clean_db):
        """
        Test that approve returns summary of all operations

        Given: A conversation with pending operations
        When: Calling approve_and_execute_all
        Then: Should return detailed summary of operations
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        conversation_id = "conv_summary_test"

        sandbox = manager.get_or_create_sandbox(clean_db, conversation_id)

        patient = Patient(
            patient_id="summary-test",
            name="Summary Test",
            age=40,
            gender="female",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()

        # Approve
        result = manager.approve_and_execute_all(clean_db, conversation_id)

        # Verify summary
        assert "operations" in result
        assert len(result["operations"]) == 1

        op = result["operations"][0]
        assert "operation_type" in op
        assert "table_name" in op
        assert "details" in op
        assert "timestamp" in op

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_reject_operations_drops_all(self, clean_db):
        """
        Test that rejecting operations drops them all

        Given: A conversation with pending operations
        When: Calling reject_and_discard_all
        Then: All operations should be discarded and not committed
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        conversation_id = "conv_reject_test"

        sandbox = manager.get_or_create_sandbox(clean_db, conversation_id)

        patient = Patient(
            patient_id="reject-test",
            name="Reject Test",
            age=50,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()

        assert sandbox.has_pending_operations()

        # Reject
        result = manager.reject_and_discard_all(conversation_id)

        assert result["success"] is True
        assert result["discarded_count"] == 1

        # Verify not committed
        patient_check = clean_db.query(Patient).filter_by(patient_id="reject-test").first()
        assert patient_check is None

        # Verify sandbox removed from manager
        assert conversation_id not in manager.sessions


class TestSandboxLifecycleManagement:
    """Test suite for sandbox lifecycle management"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_remove_sandbox(self):
        """
        Test removing a sandbox from manager

        Given: A manager with a sandbox
        When: Calling remove_sandbox
        Then: Sandbox should be removed from sessions dict
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        sandbox = manager.get_or_create_sandbox(real_session, "conv_remove")
        assert "conv_remove" in manager.sessions

        manager.remove_sandbox("conv_remove")

        assert "conv_remove" not in manager.sessions

        sandbox.close()
        real_session.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_has_pending_operations(self, clean_db):
        """
        Test checking if conversation has pending operations

        Given: A manager with a sandbox and pending operations
        When: Calling has_pending_operations
        Then: Should return True if operations exist
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()

        # No operations initially
        sandbox = manager.get_or_create_sandbox(clean_db, "conv_pending")
        assert not manager.has_pending_operations("conv_pending")

        # Add operation
        patient = Patient(
            patient_id="pending-test",
            name="Pending Test",
            age=30,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()

        assert manager.has_pending_operations("conv_pending")

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_get_pending_operations_summary(self, clean_db):
        """
        Test getting summary of pending operations

        Given: A manager with a sandbox and pending operations
        When: Calling get_pending_operations_summary
        Then: Should return list of operations
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()

        sandbox = manager.get_or_create_sandbox(clean_db, "conv_summary")

        patient = Patient(
            patient_id="summary-op-test",
            name="Summary Op Test",
            age=35,
            gender="female",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()

        summary = manager.get_pending_operations_summary("conv_summary")

        assert len(summary) == 1
        assert "operation_type" in summary[0]
        assert "table_name" in summary[0]

        sandbox.close()


class TestErrorHandlingAndEdgeCases:
    """Test suite for error handling and edge cases"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_approve_with_no_pending_operations(self):
        """
        Test approving when no operations pending

        Given: A conversation with no pending operations
        When: Calling approve_and_execute_all
        Then: Should return success=False with appropriate message
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        # Create sandbox but no operations
        manager.get_or_create_sandbox(real_session, "conv_no_ops")

        result = manager.approve_and_execute_all(real_session, "conv_no_ops")

        assert result["success"] is False
        assert "no pending" in result["message"].lower()

        real_session.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_approve_nonexistent_conversation(self):
        """
        Test approving for nonexistent conversation

        Given: A manager without the conversation
        When: Calling approve_and_execute_all
        Then: Should return error
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        result = manager.approve_and_execute_all(real_session, "conv_nonexistent")

        assert result["success"] is False
        assert "not found" in result["message"].lower()

        real_session.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_get_pending_for_nonexistent_conversation(self):
        """
        Test getting pending operations for nonexistent conversation

        Given: A manager without the conversation
        When: Calling has_pending_operations
        Then: Should return False
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()

        assert not manager.has_pending_operations("conv_nonexistent")

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_multiple_conversations_isolated(self):
        """
        Test that different conversations have isolated sandboxes

        Given: Multiple conversations with operations
        When: Performing operations on each
        Then: Each conversation should have its own sandbox
        """
        from backend.services.session_sandbox_manager import SandboxSessionManager

        manager = SandboxSessionManager()
        real_session = SessionLocal()

        # Create two conversations
        sandbox1 = manager.get_or_create_sandbox(real_session, "conv_iso_1")
        sandbox2 = manager.get_or_create_sandbox(real_session, "conv_iso_2")

        # They should be different instances
        assert sandbox1 is not sandbox2
        assert sandbox1.conversation_id == "conv_iso_1"
        assert sandbox2.conversation_id == "conv_iso_2"

        # Both should be in manager
        assert "conv_iso_1" in manager.sessions
        assert "conv_iso_2" in manager.sessions
        assert len(manager.sessions) == 2

        sandbox1.close()
        sandbox2.close()
        real_session.close()


# ============================================
# Test Fixtures
# ============================================

@pytest.fixture
def clean_db():
    """Create a fresh database for each test"""
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


@pytest.fixture
def test_patient(clean_db):
    """Create a test patient"""
    patient = patient_crud.create(
        clean_db,
        PatientCreate(
            name="Test Patient",
            age=30,
            gender="male"
        )
    )
    clean_db.commit()

    return patient
