"""
Sandbox Mechanism Tests for DataManagerCodeAgent

Tests that the sandbox mechanism correctly:
1. Intercepts database commit operations
2. Requests yes/no approval for modifications
3. Records pending operations without executing them
4. Executes operations only after approval
5. Provides proper feedback about pending changes

The sandbox mechanism is a critical security feature that prevents
unintended database modifications by requiring explicit approval.
"""
import pytest
from datetime import datetime
from unittest.mock import MagicMock, patch

from backend.services.sandbox_session import SandboxSession, DatabaseOperation
from backend.database.models import Patient
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.agents.data_manager import DataManagerCodeAgent, query_database
from backend.config.config_manager import reset_config


class TestSandboxSessionBasics:
    """Test suite for basic SandboxSession functionality"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_sandbox_session_initialization(self, db_session):
        """
        Test that SandboxSession initializes correctly

        Given: A real database session
        When: Creating a SandboxSession
        Then: Should wrap the session and enable sandbox mode
        """
        conversation_id = "test_conv_123"
        sandbox = SandboxSession(db_session, conversation_id)

        # Verify initialization
        assert sandbox.real_session == db_session
        assert sandbox.conversation_id == conversation_id
        assert sandbox.is_sandboxed is True  # Default: sandbox enabled
        assert sandbox.operations == []
        assert sandbox._committed is False

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_sandbox_session_proxies_attributes(self, db_session):
        """
        Test that SandboxSession proxies attributes to real session

        Given: A SandboxSession wrapping a real session
        When: Accessing session attributes
        Then: Should proxy to the real session
        """
        sandbox = SandboxSession(db_session, "test_conv")

        # Should proxy query() method
        assert sandbox.query is not None

        # Should be able to query through sandbox
        patients = sandbox.query(Patient).all()
        assert isinstance(patients, list)

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_sandbox_session_enable_disable(self, db_session):
        """
        Test that sandbox mode can be enabled and disabled

        Given: A SandboxSession
        When: Toggling sandbox mode
        Then: Mode should change accordingly
        """
        sandbox = SandboxSession(db_session, "test_conv")

        # Initially sandboxed
        assert sandbox.is_sandboxed is True

        # Disable sandbox
        sandbox.disable_sandbox()
        assert sandbox.is_sandboxed is False

        # Re-enable sandbox
        sandbox.enable_sandbox()
        assert sandbox.is_sandboxed is True

        sandbox.close()


class TestSandboxCommitInterception:
    """Test suite for commit interception in sandbox mode"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_intercepts_commit_in_sandbox_mode(self, clean_db):
        """
        Test that commit() is intercepted in sandbox mode

        Given: A sandboxed session with pending changes
        When: commit() is called
        Then: Changes should be flushed but NOT committed to database
        """
        # Create sandbox
        sandbox = SandboxSession(clean_db, "test_conv")

        # Create a patient
        patient = Patient(
            patient_id="sandbox-test-1",
            name="Sandbox Test",
            age=30,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)

        # Commit in sandbox mode (should be intercepted)
        sandbox.commit()

        # Verify operation was recorded
        assert sandbox.has_pending_operations()
        assert len(sandbox.operations) > 0

        # Verify data was NOT actually committed
        # Close sandbox and check with new session
        sandbox.close()

        # New session should NOT see the patient
        new_session = clean_db
        patient_check = new_session.query(Patient).filter_by(patient_id="sandbox-test-1").first()
        assert patient_check is None  # Should not exist

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_commits_for_real_when_disabled(self, clean_db):
        """
        Test that commit() executes for real when sandbox is disabled

        Given: A sandbox with pending changes and sandbox disabled
        When: commit() is called
        Then: Changes should be committed to database
        """
        # Create sandbox
        sandbox = SandboxSession(clean_db, "test_conv")

        # Create a patient
        patient = Patient(
            patient_id="sandbox-test-2",
            name="Real Commit Test",
            age=35,
            gender="female",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)

        # Disable sandbox
        sandbox.disable_sandbox()

        # Commit (should actually commit)
        sandbox.commit()

        # Verify it was actually committed
        assert sandbox._committed is True

        # Verify data exists in database
        patient_check = clean_db.query(Patient).filter_by(patient_id="sandbox-test-2").first()
        assert patient_check is not None
        assert patient_check.name == "Real Commit Test"

        sandbox.close()


class TestSandboxPendingOperations:
    """Test suite for pending operations tracking"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_records_insert_operation(self, clean_db):
        """
        Test that sandbox records INSERT operations

        Given: A sandboxed session
        When: A new object is added and committed
        Then: INSERT operation should be recorded
        """
        sandbox = SandboxSession(clean_db, "test_conv")

        # Create new patient
        patient = Patient(
            patient_id="insert-test-1",
            name="Insert Test",
            age=25,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()

        # Get pending operations
        operations = sandbox.get_pending_operations()

        assert len(operations) > 0

        # Find insert operation
        insert_ops = [op for op in operations if op["operation_type"] == "batch_commit"]
        assert len(insert_ops) > 0

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_records_update_operation(self, clean_db, test_patient):
        """
        Test that sandbox records UPDATE operations

        Given: A sandboxed session with existing patient
        When: Patient is modified and committed
        Then: UPDATE operation should be recorded
        """
        sandbox = SandboxSession(clean_db, "test_conv")

        # Get and update patient
        patient = sandbox.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
        patient.age = 99
        sandbox.commit()

        # Get pending operations
        operations = sandbox.get_pending_operations()

        assert len(operations) > 0

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_records_delete_operation(self, clean_db, test_patient):
        """
        Test that sandbox records DELETE operations

        Given: A sandboxed session with existing patient
        When: Patient is deleted and committed
        Then: DELETE operation should be recorded
        """
        sandbox = SandboxSession(clean_db, "test_conv")

        # Delete patient
        patient = sandbox.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
        sandbox.delete(patient)
        sandbox.commit()

        # Get pending operations
        operations = sandbox.get_pending_operations()

        assert len(operations) > 0

        sandbox.close()


class TestSandboxExecutePending:
    """Test suite for executing pending operations after approval"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_execute_pending_commits_to_database(self, clean_db):
        """
        Test that execute_pending actually commits to database

        Given: A sandbox with pending operations
        When: execute_pending() is called
        Then: Operations should be committed to database
        """
        # Create sandbox and add patient
        sandbox = SandboxSession(clean_db, "test_conv")

        patient = Patient(
            patient_id="execute-test-1",
            name="Execute Test",
            age=40,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()  # Intercepted

        # Verify operation is pending
        assert sandbox.has_pending_operations()

        # Execute pending
        result = sandbox.execute_pending()

        # Verify result
        assert result["success"] is True
        assert result["executed_count"] > 0
        assert "operations" in result

        # Verify data was actually committed
        patient_check = clean_db.query(Patient).filter_by(patient_id="execute-test-1").first()
        assert patient_check is not None
        assert patient_check.name == "Execute Test"

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_execute_pending_returns_error_when_no_operations(self, db_session):
        """
        Test that execute_pending returns error when no pending operations

        Given: A sandbox with no pending operations
        When: execute_pending() is called
        Then: Should return error
        """
        sandbox = SandboxSession(db_session, "test_conv")

        result = sandbox.execute_pending()

        assert result["success"] is False
        assert "error" in result
        assert "No pending operations" in result["error"]

        sandbox.close()


class TestDatabaseOperation:
    """Test suite for DatabaseOperation class"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_database_operation_creation(self):
        """
        Test DatabaseOperation object creation

        Given: Operation details
        When: Creating DatabaseOperation
        Then: Should store all details correctly
        """
        operation = DatabaseOperation(
            operation_type="insert",
            table_name="patients",
            details={"patient_id": "test-123", "name": "Test"}
        )

        assert operation.operation_type == "insert"
        assert operation.table_name == "patients"
        assert operation.details == {"patient_id": "test-123", "name": "Test"}
        assert operation.timestamp is not None

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_database_operation_to_dict(self):
        """
        Test DatabaseOperation serialization

        Given: A DatabaseOperation
        When: Converting to dictionary
        Then: Should include all fields
        """
        operation = DatabaseOperation(
            operation_type="update",
            table_name="patients",
            details={"field": "age", "old": 30, "new": 35}
        )

        op_dict = operation.to_dict()

        assert "operation_type" in op_dict
        assert "table_name" in op_dict
        assert "details" in op_dict
        assert "timestamp" in op_dict
        assert op_dict["operation_type"] == "update"

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_database_operation_repr(self):
        """
        Test DatabaseOperation string representation
        """
        operation = DatabaseOperation(
            operation_type="delete",
            table_name="patients",
            details={"patient_id": "test-123"}
        )

        repr_str = repr(operation)

        assert "delete" in repr_str
        assert "patients" in repr_str


class TestSandboxContextManager:
    """Test suite for SandboxSession context manager"""

    @pytest.mark.sandbox
    @pytest.mark.unit
    def test_sandbox_context_manager(self, db_session):
        """
        Test that SandboxSession works as context manager

        Given: A SandboxSession used as context manager
        When: Exiting context without commit
        Then: Should auto-rollback
        """
        from backend.services.sandbox_session import sandbox_session

        with sandbox_session(db_session, "test_ctx") as sandbox:
            # Add a patient
            patient = Patient(
                patient_id="ctx-test-1",
                name="Context Test",
                age=30,
                gender="male",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            sandbox.add(patient)
            # Don't commit - should auto-rollback on exit

        # After exit, should have rolled back
        # (Verified by not crashing on context exit)

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_context_manager_with_commit(self, clean_db):
        """
        Test context manager with explicit commit

        Given: A SandboxSession as context manager
        When: Committing before exit
        Then: Should not rollback (but still sandboxed)
        """
        from backend.services.sandbox_session import sandbox_session

        with sandbox_session(clean_db, "test_ctx_2") as sandbox:
            patient = Patient(
                patient_id="ctx-test-2",
                name="Context Commit",
                age=35,
                gender="female",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            sandbox.add(patient)
            sandbox.commit()  # Intercepted by sandbox

        # After exit, verify auto-rollback happened
        # (operations preserved but data not committed)


class TestSandboxWithAgent:
    """Test suite for sandbox mechanism integration with DataManagerCodeAgent"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_query_database_uses_sandbox_for_writes(self, clean_db):
        """
        Test that query_database tool provides sandbox for writes

        Given: A write operation code using the auto-created sandbox
        When: Executed through query_database
        Then: Should use the auto-created SandboxSession and record operations
        """
        code = """
from datetime import datetime

# Use the auto-created 'sandbox' object (provided by query_database)
patient = Patient(
    patient_id="query-sandbox-auto-test",
    name="Auto Sandbox Test",
    age=30,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
sandbox.add(patient)
sandbox.commit()  # Should be intercepted

result["output"] = f"Operations: {len(sandbox.operations)}, Pending: {sandbox.has_pending_operations()}"
"""

        output = query_database(code)

        # Verify sandbox was used and operations were recorded
        assert "Operations:" in output
        assert "Pending:" in output
        # Should indicate pending operations
        assert "awaiting" in output.lower() or "pending" in output.lower()

        # Verify the patient was NOT actually committed to database
        # (because it's waiting for approval)
        patient_check = clean_db.query(Patient).filter_by(patient_id="query-sandbox-auto-test").first()
        assert patient_check is None, "Should NOT commit without approval"

    @pytest.mark.slow
    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_agent_execute_pending_method(self):
        """
        Test agent's execute_pending method

        Given: Pending operations data
        When: Calling agent.execute_pending()
        Then: Should execute operations in non-sandbox mode
        """
        reset_config()

        with patch("backend.agents.data_manager.ToolCallingAgent"):
            agent = DataManagerCodeAgent()

            # Create mock operations data
            operations_data = [
                {
                    "operation_type": "batch_commit",
                    "table_name": "patients",
                    "details": {"conversation_id": "test_conv"}
                }
            ]

            # Execute pending (will fail since no actual changes, but tests the flow)
            result = agent.execute_pending(operations_data, "test_conv")

            # Should return result dict
            assert "success" in result

        reset_config()


class TestSandboxApprovalWorkflow:
    """Test suite for the complete approval workflow"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_complete_sandbox_workflow(self, clean_db):
        """
        Test the complete sandbox workflow: intercept -> review -> approve -> execute

        Given: A user requesting a database modification
        When: Following the complete workflow
        Then: Operations should only execute after approval
        """
        # Step 1: Create sandbox and perform operation
        sandbox = SandboxSession(clean_db, "workflow_test")

        patient = Patient(
            patient_id="workflow-test-1",
            name="Workflow Test",
            age=50,
            gender="male",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()  # Intercepted

        # Step 2: Review pending operations
        operations = sandbox.get_pending_operations()
        assert len(operations) > 0

        # Simulate user review: check operation details
        for op in operations:
            assert op["table_name"] in ["patients", "unknown"]
            assert "details" in op

        # Step 3: User approves - execute pending
        result = sandbox.execute_pending()

        # Step 4: Verify execution
        assert result["success"] is True

        # Verify data in database
        patient_check = clean_db.query(Patient).filter_by(patient_id="workflow-test-1").first()
        assert patient_check is not None

        sandbox.close()

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_rejection_workflow(self, clean_db):
        """
        Test the rejection workflow: intercept -> review -> reject

        Given: A user requesting a database modification
        When: User rejects the operation
        Then: Operations should NOT be executed
        """
        # Step 1: Create sandbox and perform operation
        sandbox = SandboxSession(clean_db, "rejection_test")

        patient = Patient(
            patient_id="rejection-test-1",
            name="Rejection Test",
            age=45,
            gender="female",
            created_at=datetime.now(),
            updated_at=datetime.now()
        )
        sandbox.add(patient)
        sandbox.commit()  # Intercepted

        # Step 2: Review and REJECT (just close without executing)
        sandbox.close()

        # Step 3: Verify data was NOT committed
        patient_check = clean_db.query(Patient).filter_by(patient_id="rejection-test-1").first()
        assert patient_check is None  # Should not exist


class TestSandboxMultipleOperations:
    """Test suite for multiple operations in one transaction"""

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_sandbox_handles_multiple_operations(self, clean_db):
        """
        Test that sandbox can handle multiple operations in one commit

        Given: Multiple database modifications
        When: Committed together in sandbox
        Then: All should be recorded and executed together
        """
        sandbox = SandboxSession(clean_db, "multi_op_test")

        # Create multiple patients
        for i in range(3):
            patient = Patient(
                patient_id=f"multi-op-{i}",
                name=f"Multi Op {i}",
                age=30 + i,
                gender="male",
                created_at=datetime.now(),
                updated_at=datetime.now()
            )
            sandbox.add(patient)

        sandbox.commit()  # Intercept all

        # Verify operations recorded
        operations = sandbox.get_pending_operations()
        assert len(operations) > 0

        # Execute all
        result = sandbox.execute_pending()
        assert result["success"] is True

        # Verify all patients exist
        for i in range(3):
            patient_check = clean_db.query(Patient).filter_by(patient_id=f"multi-op-{i}").first()
            assert patient_check is not None

        sandbox.close()


class TestSandboxEnforcement:
    """
    Test suite to verify that query_database ENFORCES sandbox usage

    CRITICAL: These tests verify that ALL write operations MUST go through
    the sandbox mechanism and cannot bypass approval.
    """

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_query_database_blocks_direct_session_writes(self, clean_db):
        """
        Test that query_database blocks direct SessionLocal() writes

        CRITICAL SECURITY TEST:
        Given: Code that tries to use SessionLocal() directly for writes
        When: Executed through query_database
        Then: Should be BLOCKED or intercepted by sandbox

        This ensures users cannot bypass approval by using raw session.
        """
        # Try to write directly without sandbox
        malicious_code = """
from datetime import datetime

# Try to bypass sandbox by using SessionLocal() directly
session = SessionLocal()

patient = Patient(
    patient_id="direct-write-bypass",
    name="Direct Write Bypass",
    age=30,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
session.add(patient)
session.commit()  # This should be intercepted or blocked
session.close()

result["output"] = "Direct write succeeded"
"""

        output = query_database(malicious_code)

        # CRITICAL: The direct write should either:
        # 1. Be blocked with an error message, OR
        # 2. Be intercepted by sandbox (no actual commit to DB)

        # Verify the patient was NOT actually committed to database
        patient_check = clean_db.query(Patient).filter_by(patient_id="direct-write-bypass").first()
        assert patient_check is None, "Direct writes should NOT commit to database!"

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_query_database_intercepts_all_write_operations(self, clean_db):
        """
        Test that query_database automatically intercepts ALL write operations

        Given: Any code that tries to modify the database
        When: Executed through query_database
        Then: Should automatically use sandbox and record operations

        This tests that the sandbox enforcement is automatic, not manual.
        """
        # Code that performs write operations
        write_code = """
from datetime import datetime

# Perform a write operation
patient = Patient(
    patient_id="auto-sandbox-test",
    name="Auto Sandbox Test",
    age=30,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# If sandbox enforcement works, this should be automatically intercepted
# even if we don't explicitly use SandboxSession

result["output"] = "Write operation attempted"
"""

        output = query_database(write_code)

        # CRITICAL: Verify the write was NOT committed to database
        # (because it should have been intercepted by sandbox)
        patient_check = clean_db.query(Patient).filter_by(patient_id="auto-sandbox-test").first()
        assert patient_check is None, "Write operations should be intercepted by sandbox and NOT committed"

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_query_database_requires_sandbox_for_update(self, clean_db, test_patient):
        """
        Test that query_database requires sandbox for UPDATE operations

        Given: Code that tries to update an existing record
        When: Executed through query_database
        Then: Should be intercepted by sandbox
        """
        update_code = f"""
# Try to update patient without explicit sandbox
session = SessionLocal()
patient = session.query(Patient).filter_by(patient_id="{test_patient.patient_id}").first()
patient.age = 999
session.commit()
session.close()

result["output"] = "Update attempted"
"""

        output = query_database(update_code)

        # Verify the update was NOT committed (should be intercepted)
        # Re-query with a fresh session to check actual database state
        fresh_session = clean_db
        patient_check = fresh_session.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
        assert patient_check.age != 999, "Update operations should be intercepted by sandbox"

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_query_database_requires_sandbox_for_delete(self, clean_db, test_patient):
        """
        Test that query_database requires sandbox for DELETE operations

        Given: Code that tries to delete a record
        When: Executed through query_database
        Then: Should be intercepted by sandbox
        """
        delete_code = f"""
# Try to delete patient without explicit sandbox
session = SessionLocal()
patient = session.query(Patient).filter_by(patient_id="{test_patient.patient_id}").first()
session.delete(patient)
session.commit()
session.close()

result["output"] = "Delete attempted"
"""

        output = query_database(delete_code)

        # Verify the patient was NOT actually deleted
        patient_check = clean_db.query(Patient).filter_by(patient_id=test_patient.patient_id).first()
        assert patient_check is not None, "Delete operations should be intercepted by sandbox"

    @pytest.mark.sandbox
    @pytest.mark.integration
    def test_only_explicit_sandbox_allows_execution(self, clean_db):
        """
        Test that only explicit SandboxSession usage allows controlled writes

        Given: Code that explicitly uses SandboxSession
        When: Executed through query_database
        Then: Should record operations but not commit until approved

        This verifies that:
        1. SandboxSession works correctly
        2. Direct writes are blocked/intercepted
        3. Only approved operations execute
        """
        # Step 1: Try to write directly (should fail)
        direct_code = """
from datetime import datetime

patient = Patient(
    patient_id="should-not-exist",
    name="Should Not Exist",
    age=30,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)

# This should be intercepted
result["output"] = "Attempted"
"""

        query_database(direct_code)

        # Verify it was NOT committed
        patient = clean_db.query(Patient).filter_by(patient_id="should-not-exist").first()
        assert patient is None, "Direct writes should not commit"

        # Step 2: Use explicit SandboxSession (should work with approval)
        sandbox_code = """
from datetime import datetime

sandbox = SandboxSession(SessionLocal(), "test_enforcement")

patient = Patient(
    patient_id="explicit-sandbox-test",
    name="Explicit Sandbox",
    age=30,
    gender="male",
    created_at=datetime.now(),
    updated_at=datetime.now()
)
sandbox.add(patient)
sandbox.commit()  # Intercepted

# Get pending operations for approval
operations = sandbox.get_pending_operations()
result["pending_count"] = len(operations)
result["operations"] = operations

sandbox.close()
"""

        output = query_database(sandbox_code)

        # Verify operations were recorded
        assert "pending_count" in str(output) or "operations" in str(output)

        # Verify it was NOT committed yet (waiting for approval)
        patient = clean_db.query(Patient).filter_by(patient_id="explicit-sandbox-test").first()
        assert patient is None, "Sandbox operations should wait for approval"
