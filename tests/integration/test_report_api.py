"""
Integration tests for Medical Report API endpoints.

Tests the full API flow for report creation, approval, and retrieval.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.crud import PatientCRUD, ConversationCRUD, ReportCRUD
from backend.database.schemas import PatientCreate, ConversationCreate, ReportCreate, ReportUpdate, ReportApproval
from backend.api.server import app


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
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


@pytest.fixture
def sample_patient_data():
    """Sample patient data for testing."""
    return {
        "name": "Test Patient",
        "age": 45,
        "gender": "male",
        "phone": "1234567890"
    }


@pytest.fixture
def sample_report_data():
    """Sample report data for testing."""
    return {
        "summary": "Patient presents with elevated blood pressure.",
        "key_findings": "BP: 145/95 mmHg, Family history of hypertension",
        "recommendations": "Lifestyle modifications, follow-up in 2 weeks",
        "follow_up": "Recheck blood pressure in 2 weeks"
    }


class TestReportAPIEndpoints:
    """Tests for report API endpoints using direct database calls."""

    def test_create_report(self, db_session):
        """Test creating a report via CRUD."""
        # Create patient
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))

        # Create conversation
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Hypertension diagnosis",
            model_type="DrHyper"
        ))

        # Create report
        report = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Test summary",
            key_findings="Test findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up"
        ))

        assert report.report_id is not None
        assert report.status == "pending"
        assert report.summary == "Test summary"

    def test_approve_report(self, db_session):
        """Test approving a report."""
        # Create prerequisites
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Hypertension diagnosis"
        ))
        report = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Test"
        ))

        # Approve
        approved = ReportCRUD.approve(db_session, report.report_id, ReportApproval(
            approved=True,
            notes="Reviewed and approved"
        ))

        assert approved.status == "approved"
        assert approved.approved_at is not None

    def test_reject_report(self, db_session):
        """Test rejecting a report."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Test"
        ))
        report = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Test"
        ))

        # Reject
        rejected = ReportCRUD.approve(db_session, report.report_id, ReportApproval(
            approved=False,
            notes="Needs revision"
        ))

        assert rejected.status == "rejected"

    def test_get_report_by_conversation(self, db_session):
        """Test retrieving report by conversation ID."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Test"
        ))
        created = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Test summary"
        ))

        retrieved = ReportCRUD.get_by_conversation(db_session, conv.conversation_id)

        assert retrieved is not None
        assert retrieved.report_id == created.report_id

    def test_list_reports_by_patient(self, db_session):
        """Test listing reports for a patient."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv1 = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Consultation 1"
        ))
        conv2 = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Consultation 2"
        ))

        # Create two reports
        ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv1.conversation_id,
            summary="Report 1"
        ))
        ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv2.conversation_id,
            summary="Report 2"
        ))

        reports, total = ReportCRUD.list_by_patient(db_session, patient.patient_id)

        assert total == 2
        assert len(reports) == 2

    def test_get_approved_reports(self, db_session):
        """Test getting only approved reports for a patient."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv1 = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Consultation 1"
        ))
        conv2 = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Consultation 2"
        ))

        # Create two reports
        report1 = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv1.conversation_id,
            summary="Report 1"
        ))
        report2 = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv2.conversation_id,
            summary="Report 2"
        ))

        # Approve only report1
        ReportCRUD.approve(db_session, report1.report_id, ReportApproval(approved=True))

        approved = ReportCRUD.get_approved_by_patient(db_session, patient.patient_id)

        assert len(approved) == 1
        assert approved[0].report_id == report1.report_id

    def test_delete_report(self, db_session):
        """Test deleting a report."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Test"
        ))
        report = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Test"
        ))

        result = ReportCRUD.delete(db_session, report.report_id)
        assert result is True

        deleted = ReportCRUD.get(db_session, report.report_id)
        assert deleted is None

    def test_update_report(self, db_session):
        """Test updating report content."""
        patient = PatientCRUD.create(db_session, PatientCreate(
            name="Test Patient",
            age=45,
            gender="male"
        ))
        conv = ConversationCRUD.create(db_session, ConversationCreate(
            patient_id=patient.patient_id,
            target="Test"
        ))
        report = ReportCRUD.create(db_session, ReportCreate(
            patient_id=patient.patient_id,
            conversation_id=conv.conversation_id,
            summary="Original summary"
        ))

        updated = ReportCRUD.update(db_session, report.report_id, ReportUpdate(
            summary="Updated summary",
            key_findings="New findings"
        ))

        assert updated.summary == "Updated summary"
        assert updated.key_findings == "New findings"