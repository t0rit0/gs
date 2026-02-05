"""
Tests for SandboxSession

Tests cover:
1. Sandbox interception of commits
2. Operation recording and tracking
3. Approval workflow execution
4. Rollback functionality
5. Error handling
"""

import pytest
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database.base import SessionLocal, engine, Base
from backend.services.sandbox_session import (
    SandboxSession,
    sandbox_session,
    DatabaseOperation
)
from backend.database.models import Patient
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate


class TestSandboxSession:
    """Test suite for SandboxSession functionality"""

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

    def test_sandbox_intercepts_commit(self, db_session: Session):
        """
        Test that sandbox mode intercepts commit operations

        Given: A sandbox session wrapping a real session
        When: Performing database operations and calling commit()
        Then: Changes should be recorded but not actually committed
        """
        # Arrange
        patient_id = self._create_test_patient()

        # Create a fresh sandbox session (independent of db_session)
        sandbox = SandboxSession(SessionLocal(), "test_conv")
        try:
            # Act: Modify patient and commit in sandbox
            test_patient = patient_crud.get(sandbox, patient_id)
            assert test_patient is not None
            test_patient.name = "Modified Name"
            sandbox.commit()

            # Assert: Operation recorded but not committed
            assert sandbox.has_pending_operations()
            assert len(sandbox.get_pending_operations()) == 1
        finally:
            sandbox.rollback()

        # Verify change not in actual database
        verify_session = SessionLocal()
        try:
            original_patient = patient_crud.get(verify_session, patient_id)
            assert original_patient.name == "Test Patient"  # Unchanged
        finally:
            verify_session.close()

    def test_sandbox_records_operation_details(self, db_session: Session):
        """
        Test that sandbox correctly records operation details

        Given: A sandbox session
        When: Making changes to a patient
        Then: Operation details should include field changes
        """
        # Arrange
        patient_id = self._create_test_patient()

        sandbox = SandboxSession(SessionLocal(), "test_conv")
        try:
            # Act
            test_patient = patient_crud.get(sandbox, patient_id)
            test_patient.age = 35
            test_patient.name = "Updated Name"
            sandbox.commit()

            # Assert
            operations = sandbox.get_pending_operations()
            assert len(operations) == 1

            op = operations[0]
            assert op["operation_type"] == "batch_commit"
            assert "pending_changes" in op["details"]

            changes = op["details"]["pending_changes"]
            assert len(changes) > 0

            # Check update operation
            update_ops = [c for c in changes if c["type"] == "update"]
            assert len(update_ops) == 1

            update_change = update_ops[0]
            assert "changes" in update_change
            assert "age" in update_change["changes"]
            assert update_change["changes"]["age"]["old"] == 30
            assert update_change["changes"]["age"]["new"] == 35
        finally:
            sandbox.rollback()

    def test_execute_pending_operations(self, db_session: Session):
        """
        Test that pending operations can be executed after approval

        Given: A sandbox session with pending operations
        When: Disabling sandbox and committing the same session
        Then: Changes should be actually committed to database
        """
        # Arrange
        patient_id = self._create_test_patient()

        # Act: Create pending changes in sandbox mode
        sandbox = SandboxSession(SessionLocal(), "test_conv")
        test_patient = patient_crud.get(sandbox, patient_id)
        test_patient.age = 40
        sandbox.commit()

        # Assert: Changes recorded but not committed yet
        operations = sandbox.get_pending_operations()
        assert len(operations) == 1

        verify_session = SessionLocal()
        try:
            original = patient_crud.get(verify_session, patient_id)
            assert original.age == 30  # Still original value
        finally:
            verify_session.close()

        # Act: Disable sandbox and execute (simulating approval)
        sandbox.disable_sandbox()
        result = sandbox.execute_pending()
        sandbox.close()

        # Assert: Now committed
        assert result["success"] is True

        verify_session = SessionLocal()
        try:
            updated = patient_crud.get(verify_session, patient_id)
            assert updated.age == 40  # Value updated
        finally:
            verify_session.close()

    def test_sandbox_context_manager_auto_rollback(self, db_session: Session):
        """
        Test that context manager auto-rolls back on exit

        Given: A sandbox session with uncommitted changes
        When: Exiting the context without committing
        Then: Changes should be automatically rolled back
        """
        # Arrange
        patient_id = self._create_test_patient()

        # Act: Create sandbox, make changes, exit without commit
        with SandboxSession(SessionLocal(), "test_conv") as sandbox:
            test_patient = patient_crud.get(sandbox, patient_id)
            test_patient.age = 50
            # No commit called

        # Assert: Original patient unchanged
        verify_session = SessionLocal()
        try:
            original = patient_crud.get(verify_session, patient_id)
            assert original.age == 30
        finally:
            verify_session.close()

    def test_add_health_metric_sandbox(self, db_session: Session):
        """
        Test adding health metric in sandbox mode

        Given: A patient
        When: Adding health metric using CRUD in sandbox
        Then: Metric should be recorded but not added
        """
        # Arrange
        patient_id = self._create_test_patient()

        # Act: Add health metric in sandbox
        with SandboxSession(SessionLocal(), "test_conv") as sandbox:
            patient_crud.add_health_metric(
                sandbox,
                patient_id,
                metric_name="Systolic Blood Pressure",
                value=150,
                unit="mmHg",
                notes="Test measurement"
            )
            sandbox.commit()

            # But operation was recorded
            operations = sandbox.get_pending_operations()
            assert len(operations) == 1

        # Assert: Not actually added to database
        verify_session = SessionLocal()
        try:
            original = patient_crud.get(verify_session, patient_id)
            assert len(original.health_metrics or []) == 0
        finally:
            verify_session.close()

    def test_query_operations_work_in_sandbox(self, db_session: Session):
        """
        Test that query operations work normally in sandbox

        Given: A patient with data
        When: Querying in sandbox mode
        Then: Queries should work normally (not intercepted)
        """
        # Arrange - Create patient with health metrics
        session = SessionLocal()
        try:
            patient = patient_crud.create(
                session,
                PatientCreate(
                    name="Test Patient",
                    age=30,
                    gender="male",
                    health_metrics=[
                        {
                            "metric_name": "Systolic Blood Pressure",
                            "value": 140,
                            "unit": "mmHg",
                            "recorded_at": "2026-01-01T00:00:00"
                        }
                    ]
                )
            )
            session.commit()
            patient_id = patient.patient_id
        finally:
            session.close()

        # Act: Query in sandbox
        with SandboxSession(SessionLocal(), "test_conv") as sandbox:
            queried = patient_crud.get(sandbox, patient_id)
            metrics = queried.health_metrics or []

        # Assert: Queries work
        assert queried is not None
        assert queried.name == "Test Patient"
        assert len(metrics) == 1
        assert metrics[0]["value"] == 140

    def test_multiple_commits_recorded(self, db_session: Session):
        """
        Test that multiple commits are all recorded

        Given: A sandbox session
        When: Calling commit() multiple times
        Then: All commits should be recorded
        """
        # Arrange
        patient_id = self._create_test_patient()

        # Act: Multiple commits
        with SandboxSession(SessionLocal(), "test_conv") as sandbox:
            test_patient = patient_crud.get(sandbox, patient_id)

            test_patient.age = 31
            sandbox.commit()

            test_patient.age = 32
            sandbox.commit()

            test_patient.name = "Changed"
            sandbox.commit()

        # Assert: All operations recorded
        operations = sandbox.get_pending_operations()
        assert len(operations) == 3


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
