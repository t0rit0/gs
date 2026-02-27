"""
Real Integration Test for Patient Context with Historical Reports

Tests that historical approved reports are loaded into PatientContext
and available for EntityGraph initialization.

To run:
    uv run pytest tests/integration/test_patient_context_reports.py -v -s
"""

import pytest
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, report_crud
from backend.database.schemas import PatientCreate, ReportCreate, ReportApproval
from backend.database.models import MedicalReport
from backend.services.patient_context_builder import PatientContextBuilder


class TestPatientContextWithReports:
    """Tests for PatientContext with historical reports"""

    @pytest.fixture
    def db(self):
        """Real database session"""
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_patient(self, db):
        """Create a test patient"""
        unique_id = str(uuid.uuid4())[:8]
        patient_data = PatientCreate(
            name=f"Context Test Patient {unique_id}",
            age=45,
            gender="female",
            phone="13800138000",
            medical_history=[{
                "condition": "Hypertension",
                "diagnosis_date": "2022-06-01",
                "status": "chronic"
            }]
        )
        patient = patient_crud.create(db, patient_data)
        db.commit()
        yield patient
        # Cleanup
        try:
            db.query(MedicalReport).filter(MedicalReport.patient_id == patient.patient_id).delete()
            patient_crud.delete(db, patient.patient_id)
            db.commit()
        except:
            db.rollback()

    @pytest.mark.integration
    def test_patient_context_without_reports(self, db, test_patient):
        """Test PatientContext when patient has no historical reports"""
        print("\n=== Test: PatientContext Without Reports ===")

        context_builder = PatientContextBuilder()
        context = context_builder.build(db, test_patient.patient_id)

        assert context.patient_id == test_patient.patient_id
        assert context.basic_info["name"] == test_patient.name

        # Check no historical reports
        historical_reports = [k for k in context.patient_text_records.keys()
                            if "historical_report" in k]
        assert len(historical_reports) == 0

        # Should still have other text records
        assert "medical_history" in context.patient_text_records
        print(f"Patient text records: {list(context.patient_text_records.keys())}")
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_patient_context_with_single_report(self, db, test_patient):
        """Test PatientContext loads single approved report"""
        print("\n=== Test: PatientContext With Single Report ===")

        # Create an approved report
        report_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=f"conv_{uuid.uuid4().hex[:8]}",
            summary="Patient shows elevated blood pressure requiring monitoring.",
            key_findings="BP: 145/92 mmHg, Family history of hypertension",
            recommendations="Continue current medication, reduce salt intake",
            follow_up="Recheck in 2 weeks"
        )
        report = report_crud.create(db, report_data)
        report_crud.approve(db, report.report_id, ReportApproval(approved=True))
        db.commit()

        # Build PatientContext
        context_builder = PatientContextBuilder()
        context = context_builder.build(db, test_patient.patient_id)

        # Verify historical report loaded
        historical_reports = [k for k in context.patient_text_records.keys()
                            if "historical_report" in k]
        assert len(historical_reports) == 1

        report_key = historical_reports[0]
        report_text = context.patient_text_records[report_key]

        # Verify content includes report fields
        assert "elevated blood pressure" in report_text.lower() or "145/92" in report_text
        print(f"Historical report key: {report_key}")
        print(f"Report text preview: {report_text[:200]}...")

        # Cleanup
        report_crud.delete(db, report.report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_patient_context_with_multiple_reports(self, db, test_patient):
        """Test PatientContext loads multiple approved reports (newest first)"""
        print("\n=== Test: PatientContext With Multiple Reports ===")

        # Create multiple reports
        report_ids = []
        for i in range(5):
            report_data = ReportCreate(
                patient_id=test_patient.patient_id,
                conversation_id=f"conv_{i}_{uuid.uuid4().hex[:8]}",
                summary=f"Consultation {i+1}: BP reading taken",
                key_findings=f"Visit {i+1} findings",
                recommendations=f"Recommendations for visit {i+1}",
                follow_up="Follow-up scheduled"
            )
            report = report_crud.create(db, report_data)
            report_crud.approve(db, report.report_id, ReportApproval(approved=True))
            report_ids.append(report.report_id)
            db.commit()

        # Build PatientContext
        context_builder = PatientContextBuilder(max_historical_reports=10)
        context = context_builder.build(db, test_patient.patient_id)

        # Verify all reports loaded
        historical_reports = sorted([k for k in context.patient_text_records.keys()
                                    if "historical_report" in k])
        print(f"Found {len(historical_reports)} historical reports: {historical_reports}")

        assert len(historical_reports) == 5

        # Verify newest report is first (historical_report_1)
        first_report = context.patient_text_records["historical_report_1"]
        print(f"First (newest) report preview: {first_report[:150]}...")

        # Cleanup
        for report_id in report_ids:
            report_crud.delete(db, report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_patient_context_excludes_rejected_reports(self, db, test_patient):
        """Test PatientContext does not load rejected reports"""
        print("\n=== Test: PatientContext Excludes Rejected Reports ===")

        # Create an approved report
        approved_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=f"conv_approved_{uuid.uuid4().hex[:8]}",
            summary="Approved consultation summary",
            key_findings="Approved findings"
        )
        approved_report = report_crud.create(db, approved_data)
        report_crud.approve(db, approved_report.report_id, ReportApproval(approved=True))

        # Create a rejected report
        rejected_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=f"conv_rejected_{uuid.uuid4().hex[:8]}",
            summary="Rejected consultation summary",
            key_findings="Rejected findings"
        )
        rejected_report = report_crud.create(db, rejected_data)
        report_crud.approve(db, rejected_report.report_id, ReportApproval(approved=False))

        db.commit()

        # Build PatientContext
        context_builder = PatientContextBuilder()
        context = context_builder.build(db, test_patient.patient_id)

        # Only approved report should be loaded
        historical_reports = [k for k in context.patient_text_records.keys()
                            if "historical_report" in k]
        assert len(historical_reports) == 1

        # Verify it's the approved one
        report_text = context.patient_text_records[historical_reports[0]]
        assert "Approved" in report_text or "approved" in report_text.lower()
        assert "Rejected" not in report_text

        # Cleanup
        report_crud.delete(db, approved_report.report_id)
        report_crud.delete(db, rejected_report.report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_patient_context_limits_reports(self, db, test_patient):
        """Test PatientContext respects max_historical_reports limit"""
        print("\n=== Test: PatientContext Limits Reports ===")

        # Create more reports than the limit
        report_ids = []
        for i in range(10):
            report_data = ReportCreate(
                patient_id=test_patient.patient_id,
                conversation_id=f"conv_limit_{i}_{uuid.uuid4().hex[:8]}",
                summary=f"Report {i+1}",
                key_findings=f"Findings {i+1}"
            )
            report = report_crud.create(db, report_data)
            report_crud.approve(db, report.report_id, ReportApproval(approved=True))
            report_ids.append(report.report_id)
            db.commit()

        # Build PatientContext with limit
        context_builder = PatientContextBuilder(max_historical_reports=3)
        context = context_builder.build(db, test_patient.patient_id)

        # Should only have 3 reports
        historical_reports = [k for k in context.patient_text_records.keys()
                            if "historical_report" in k]
        assert len(historical_reports) == 3

        print(f"Limited to {len(historical_reports)} reports as expected")

        # Cleanup
        for report_id in report_ids:
            report_crud.delete(db, report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_report_text_formatting(self, db, test_patient):
        """Test that reports are formatted correctly for LLM context"""
        print("\n=== Test: Report Text Formatting ===")

        # Create report with known date
        report_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=f"conv_format_{uuid.uuid4().hex[:8]}",
            summary="Test summary for formatting",
            key_findings="Test key findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up"
        )
        report = report_crud.create(db, report_data)
        report_crud.approve(db, report.report_id, ReportApproval(approved=True))
        db.commit()

        # Build context
        context_builder = PatientContextBuilder()
        context = context_builder.build(db, test_patient.patient_id)

        # Get report text
        report_text = context.patient_text_records.get("historical_report_1", "")

        # Verify formatting
        assert "Historical Consultation Record" in report_text
        assert "Test summary for formatting" in report_text
        assert "Test key findings" in report_text
        assert "Test recommendations" in report_text

        print(f"Formatted report:\n{report_text}")

        # Cleanup
        report_crud.delete(db, report.report_id)
        db.commit()
        print("=== PASSED ===")


class TestReportCRUDReal:
    """Tests for ReportCRUD with real database"""

    @pytest.fixture
    def db(self):
        """Real database session"""
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def test_patient(self, db):
        """Create test patient"""
        patient_data = PatientCreate(
            name=f"CRUD Test Patient {uuid.uuid4().hex[:8]}",
            age=40,
            gender="male"
        )
        patient = patient_crud.create(db, patient_data)
        db.commit()
        yield patient
        try:
            db.query(MedicalReport).filter(MedicalReport.patient_id == patient.patient_id).delete()
            patient_crud.delete(db, patient.patient_id)
            db.commit()
        except:
            db.rollback()

    @pytest.mark.integration
    def test_create_and_retrieve_report(self, db, test_patient):
        """Test creating and retrieving a report"""
        print("\n=== Test: Create and Retrieve Report ===")

        conversation_id = f"conv_{uuid.uuid4().hex[:8]}"

        # Create report
        report_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=conversation_id,
            summary="Test summary",
            key_findings="Test findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up",
            full_report="Full report text"
        )
        created = report_crud.create(db, report_data)
        db.commit()

        # Retrieve by ID
        retrieved = report_crud.get(db, created.report_id)
        assert retrieved is not None
        assert retrieved.summary == "Test summary"

        # Retrieve by conversation
        by_conv = report_crud.get_by_conversation(db, conversation_id)
        assert by_conv is not None
        assert by_conv.report_id == created.report_id

        # Cleanup
        report_crud.delete(db, created.report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_update_report_before_approval(self, db, test_patient):
        """Test updating a pending report"""
        print("\n=== Test: Update Report Before Approval ===")

        # Create report
        report_data = ReportCreate(
            patient_id=test_patient.patient_id,
            conversation_id=f"conv_{uuid.uuid4().hex[:8]}",
            summary="Original summary"
        )
        report = report_crud.create(db, report_data)
        db.commit()

        # Update
        from backend.database.schemas import ReportUpdate
        updated = report_crud.update(db, report.report_id, ReportUpdate(
            summary="Updated summary",
            key_findings="New findings"
        ))
        db.commit()

        assert updated.summary == "Updated summary"
        assert updated.key_findings == "New findings"

        # Cleanup
        report_crud.delete(db, report.report_id)
        db.commit()
        print("=== PASSED ===")

    @pytest.mark.integration
    def test_list_reports_by_patient(self, db, test_patient):
        """Test listing reports for a patient"""
        print("\n=== Test: List Reports By Patient ===")

        # Create multiple reports
        for i in range(3):
            report_data = ReportCreate(
                patient_id=test_patient.patient_id,
                conversation_id=f"conv_list_{i}_{uuid.uuid4().hex[:8]}",
                summary=f"Report {i+1}"
            )
            report_crud.create(db, report_data)
        db.commit()

        # List
        reports, total = report_crud.list_by_patient(db, test_patient.patient_id)

        assert total == 3
        assert len(reports) == 3

        # Cleanup
        for r in reports:
            report_crud.delete(db, r.report_id)
        db.commit()
        print("=== PASSED ===")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])