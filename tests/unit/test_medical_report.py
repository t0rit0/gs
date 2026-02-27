"""
Unit tests for MedicalReport model and ReportCRUD operations.

Tests follow TDD approach: write tests first, then implement.
"""

import pytest
from datetime import datetime
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import Patient, Conversation, MedicalReport
from backend.database.crud import ReportCRUD, PatientCRUD, ConversationCRUD
from backend.database.schemas import (
    ReportCreate,
    ReportUpdate,
    ReportApproval,
    PatientCreate,
    ConversationCreate
)


@pytest.fixture
def db_session():
    """Create an in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def sample_patient(db_session):
    """Create a sample patient for testing."""
    patient_data = PatientCreate(
        name="Test Patient",
        age=45,
        gender="male",
        phone="1234567890"
    )
    return PatientCRUD.create(db_session, patient_data)


@pytest.fixture
def sample_conversation(db_session, sample_patient):
    """Create a sample conversation for testing."""
    conv_data = ConversationCreate(
        patient_id=sample_patient.patient_id,
        target="Hypertension diagnosis",
        model_type="DrHyper"
    )
    return ConversationCRUD.create(db_session, conv_data)


class TestMedicalReportModel:
    """Tests for MedicalReport model."""

    def test_create_medical_report(self, db_session, sample_conversation):
        """Test creating a medical report."""
        report = MedicalReport(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            report_type="hypertension_diagnosis",
            status="pending",
            summary="Patient presents with elevated blood pressure.",
            key_findings="BP: 145/95 mmHg, Family history of hypertension",
            recommendations="Lifestyle modifications, follow-up in 2 weeks",
            follow_up="Recheck blood pressure in 2 weeks"
        )

        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)

        assert report.report_id is not None
        assert report.status == "pending"
        assert report.summary == "Patient presents with elevated blood pressure."
        assert report.created_at is not None
        assert report.approved_at is None

    def test_report_default_status(self, db_session, sample_conversation):
        """Test that report status defaults to 'pending'."""
        report = MedicalReport(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id
        )

        db_session.add(report)
        db_session.commit()

        assert report.status == "pending"

    def test_report_to_dict(self, db_session, sample_conversation):
        """Test converting report to dictionary."""
        report = MedicalReport(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            report_type="hypertension_diagnosis",
            status="approved",
            summary="Test summary",
            key_findings="Test findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up",
            full_report="Full report text"
        )

        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)

        report_dict = report.to_dict()

        assert report_dict["report_id"] == report.report_id
        assert report_dict["patient_id"] == sample_conversation.patient_id
        assert report_dict["conversation_id"] == sample_conversation.conversation_id
        assert report_dict["status"] == "approved"
        assert report_dict["summary"] == "Test summary"

    def test_report_patient_relationship(self, db_session, sample_conversation):
        """Test relationship between report and patient."""
        report = MedicalReport(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)

        assert report.patient is not None
        assert report.patient.patient_id == sample_conversation.patient_id

    def test_report_conversation_relationship(self, db_session, sample_conversation):
        """Test relationship between report and conversation."""
        report = MedicalReport(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        db_session.add(report)
        db_session.commit()
        db_session.refresh(report)

        assert report.conversation is not None
        assert report.conversation.conversation_id == sample_conversation.conversation_id


class TestReportCRUD:
    """Tests for ReportCRUD operations."""

    def test_create_report(self, db_session, sample_conversation):
        """Test creating a report via CRUD."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            report_type="hypertension_diagnosis",
            summary="Test summary",
            key_findings="Test findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up",
            full_report="Full report text"
        )

        report = ReportCRUD.create(db_session, report_data)

        assert report.report_id is not None
        assert report.status == "pending"
        assert report.summary == "Test summary"

    def test_get_report(self, db_session, sample_conversation):
        """Test retrieving a report by ID."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        created_report = ReportCRUD.create(db_session, report_data)
        retrieved_report = ReportCRUD.get(db_session, created_report.report_id)

        assert retrieved_report is not None
        assert retrieved_report.report_id == created_report.report_id

    def test_get_report_by_conversation(self, db_session, sample_conversation):
        """Test retrieving a report by conversation ID."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        ReportCRUD.create(db_session, report_data)
        report = ReportCRUD.get_by_conversation(db_session, sample_conversation.conversation_id)

        assert report is not None
        assert report.conversation_id == sample_conversation.conversation_id

    def test_list_reports_by_patient(self, db_session, sample_patient, sample_conversation):
        """Test listing all reports for a patient."""
        # Create multiple reports
        for i in range(3):
            report_data = ReportCreate(
                patient_id=sample_patient.patient_id,
                conversation_id=sample_conversation.conversation_id,
                summary=f"Test summary {i}"
            )
            ReportCRUD.create(db_session, report_data)

        reports, total = ReportCRUD.list_by_patient(
            db_session,
            sample_patient.patient_id
        )

        assert total == 3
        assert len(reports) == 3

    def test_approve_report(self, db_session, sample_conversation):
        """Test approving a report."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        report = ReportCRUD.create(db_session, report_data)
        assert report.status == "pending"
        assert report.approved_at is None

        # Approve the report
        approval = ReportApproval(approved=True, notes="Reviewed and approved")
        approved_report = ReportCRUD.approve(db_session, report.report_id, approval)

        assert approved_report.status == "approved"
        assert approved_report.approved_at is not None

    def test_reject_report(self, db_session, sample_conversation):
        """Test rejecting a report."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        report = ReportCRUD.create(db_session, report_data)

        # Reject the report
        approval = ReportApproval(approved=False, notes="Needs revision")
        rejected_report = ReportCRUD.approve(db_session, report.report_id, approval)

        assert rejected_report.status == "rejected"
        assert rejected_report.approved_at is None

    def test_update_report(self, db_session, sample_conversation):
        """Test updating a report."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Original summary"
        )

        report = ReportCRUD.create(db_session, report_data)

        update_data = ReportUpdate(
            summary="Updated summary",
            key_findings="Updated findings"
        )

        updated_report = ReportCRUD.update(db_session, report.report_id, update_data)

        assert updated_report.summary == "Updated summary"
        assert updated_report.key_findings == "Updated findings"

    def test_get_approved_reports_by_patient(self, db_session, sample_patient, sample_conversation):
        """Test getting only approved reports for a patient."""
        # Create reports with different statuses
        report1 = ReportCRUD.create(db_session, ReportCreate(
            patient_id=sample_patient.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Report 1"
        ))
        report2 = ReportCRUD.create(db_session, ReportCreate(
            patient_id=sample_patient.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Report 2"
        ))

        # Approve only report1
        ReportCRUD.approve(db_session, report1.report_id, ReportApproval(approved=True))

        approved_reports = ReportCRUD.get_approved_by_patient(
            db_session,
            sample_patient.patient_id
        )

        assert len(approved_reports) == 1
        assert approved_reports[0].report_id == report1.report_id

    def test_delete_report(self, db_session, sample_conversation):
        """Test deleting a report."""
        report_data = ReportCreate(
            patient_id=sample_conversation.patient_id,
            conversation_id=sample_conversation.conversation_id,
            summary="Test summary"
        )

        report = ReportCRUD.create(db_session, report_data)
        report_id = report.report_id

        # Delete the report
        result = ReportCRUD.delete(db_session, report_id)
        assert result is True

        # Verify it's deleted
        deleted_report = ReportCRUD.get(db_session, report_id)
        assert deleted_report is None