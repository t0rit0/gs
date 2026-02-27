"""
Real Integration Test for Report Generation and Approval Flow

This test uses:
- Real database (demo.db)
- Real LLM API calls (not mocked)

Tests the complete flow:
1. Create patient
2. Run diagnostic conversation
3. Generate report
4. Approve and save report
5. Verify historical report loading

REQUIRES:
- Valid LLM API credentials in config.yaml

To run:
    uv run pytest tests/integration/test_report_flow_real.py -v -s
"""

import pytest
import asyncio
import sys
import uuid
from pathlib import Path
from datetime import datetime

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.main_agent import MainAgent
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, conversation_crud, report_crud
from backend.database.schemas import PatientCreate, ConversationCreate, ReportCreate, ReportApproval
from backend.database.models import MedicalReport
from backend.services.patient_context_builder import PatientContextBuilder


class TestReportFlowReal:
    """Real integration tests for complete report flow with LLM API calls"""

    @pytest.fixture(scope="class")
    def db(self):
        """Real database session"""
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture(scope="class")
    def agent(self):
        """Initialize MainAgent with real LLM"""
        print("\n=== Initializing MainAgent with real LLM ===")
        agent = MainAgent()
        print(f"MainAgent initialized with model: {agent.llm.model_name}")
        return agent

    @pytest.fixture
    def test_patient(self, db):
        """Create a unique test patient for each test"""
        unique_id = str(uuid.uuid4())[:8]
        patient_data = PatientCreate(
            name=f"Test Patient {unique_id}",
            age=55,
            gender="male",
            phone="13800000000",
            medical_history=[{
                "condition": "Hypertension",
                "diagnosis_date": "2023-01-01",
                "status": "chronic",
                "notes": "Diagnosed 3 years ago"
            }]
        )
        patient = patient_crud.create(db, patient_data)
        db.commit()
        print(f"Created test patient: {patient.patient_id}")
        yield patient
        # Cleanup
        try:
            db.query(MedicalReport).filter(MedicalReport.patient_id == patient.patient_id).delete()
            patient_crud.delete(db, patient.patient_id)
            db.commit()
        except:
            db.rollback()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_01_start_conversation(self, agent, test_patient):
        """Test starting a conversation with real LLM"""
        print("\n=== Test 01: Start Conversation ===")

        conversation_id = f"test_report_{uuid.uuid4().hex[:12]}"

        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=test_patient.patient_id,
            target="Hypertension diagnosis"
        )

        assert first_message is not None
        assert len(first_message) > 0
        print(f"First message: {first_message[:200]}...")

        # Cleanup
        agent.entity_graph_manager.invalidate(conversation_id)

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_02_diagnostic_conversation(self, agent, test_patient):
        """Test running a diagnostic conversation with real LLM"""
        print("\n=== Test 02: Diagnostic Conversation ===")

        conversation_id = f"test_diag_{uuid.uuid4().hex[:12]}"

        # Start conversation
        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=test_patient.patient_id,
            target="Hypertension diagnosis"
        )
        print(f"[1] First message: {first_message[:150]}...")

        # Send some diagnostic messages
        messages = [
            "Hi, I'm here for my blood pressure check.",
            "My blood pressure has been around 145/95 lately.",
            "I've been taking amlodipine 5mg daily.",
            "I sometimes get headaches in the morning.",
        ]

        for i, msg in enumerate(messages, 2):
            response, accomplish, report = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message=msg
            )
            print(f"[{i}] Response: {response[:100]}... (accomplish={accomplish})")

            if accomplish:
                print(f"Data collection complete!")
                break

        # Cleanup
        agent.entity_graph_manager.invalidate(conversation_id)

    @pytest.mark.asyncio
    @pytest.mark.integration
    @pytest.mark.slow
    async def test_03_complete_report_flow(self, agent, test_patient, db):
        """
        Complete report flow test:
        1. Run diagnostic conversation until report is generated
        2. Create and approve report
        3. Verify report saved to database
        4. Verify historical report loading in PatientContext
        """
        print("\n=== Test 03: Complete Report Flow ===")

        conversation_id = f"test_complete_{uuid.uuid4().hex[:12]}"
        patient_id = test_patient.patient_id

        # Step 1: Start conversation
        print("\n[Step 1] Starting conversation...")
        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=patient_id,
            target="Hypertension diagnosis"
        )
        print(f"First message: {first_message[:100]}...")

        # Step 2: Run diagnostic conversation
        print("\n[Step 2] Running diagnostic conversation...")
        diagnostic_responses = [
            "Hello, I'm here for my annual hypertension checkup.",
            "My recent blood pressure readings have been around 140/90.",
            "I've been diagnosed with hypertension for about 2 years now.",
            "I'm currently taking Lisinopril 10mg once daily.",
            "I exercise about 3 times a week, mostly walking.",
            "I try to limit my salt intake.",
            "My father also had high blood pressure.",
            "I occasionally get headaches when my pressure is high.",
            "No other major symptoms recently.",
        ]

        report = None
        accomplish = False

        for i, user_msg in enumerate(diagnostic_responses):
            response, accomplish, report = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message=user_msg
            )
            print(f"  [{i+1}] User: {user_msg[:50]}...")
            print(f"       AI: {response[:80]}... (accomplish={accomplish})")

            if accomplish and report:
                print("\n  *** Report generated! ***")
                break

        # Step 3: Verify report was generated
        print("\n[Step 3] Verifying report generation...")
        assert report is not None, "Report should be generated after diagnostic conversation"
        assert "summary" in report or "full_report" in report, "Report should have content"
        print(f"Report keys: {list(report.keys())}")

        # Step 4: Create report in database
        print("\n[Step 4] Creating report in database...")
        report_data = ReportCreate(
            patient_id=patient_id,
            conversation_id=conversation_id,
            summary=report.get("summary", "Generated summary"),
            key_findings=report.get("key_findings", "Key findings"),
            recommendations=report.get("recommendations", "Recommendations"),
            follow_up=report.get("follow_up", "Follow-up plan"),
            full_report=report.get("full_report", str(report))
        )
        created_report = report_crud.create(db, report_data)
        db.commit()
        print(f"Created report: {created_report.report_id}")
        assert created_report.status == "pending"

        # Step 5: Approve report
        print("\n[Step 5] Approving report...")
        approval = ReportApproval(approved=True, notes="Test approval")
        approved_report = report_crud.approve(db, created_report.report_id, approval)
        db.commit()
        assert approved_report.status == "approved"
        assert approved_report.approved_at is not None
        print(f"Report approved at: {approved_report.approved_at}")

        # Step 6: Verify report in database
        print("\n[Step 6] Verifying report in database...")
        saved_report = report_crud.get(db, created_report.report_id)
        assert saved_report is not None
        assert saved_report.status == "approved"

        # Step 7: Test PatientContextBuilder loads historical reports
        print("\n[Step 7] Testing PatientContextBuilder...")
        context_builder = PatientContextBuilder()
        patient_context = context_builder.build(db, patient_id)

        assert patient_context.patient_id == patient_id
        print(f"Patient text records keys: {list(patient_context.patient_text_records.keys())}")

        # Check for historical report
        historical_report_found = False
        for key in patient_context.patient_text_records.keys():
            if "historical_report" in key:
                historical_report_found = True
                print(f"Found historical report: {key}")
                print(f"Content preview: {patient_context.patient_text_records[key][:200]}...")

        assert historical_report_found, "Historical report should be loaded in PatientContext"

        # Step 8: Cleanup
        print("\n[Step 8] Cleaning up...")
        agent.entity_graph_manager.invalidate(conversation_id)
        report_crud.delete(db, created_report.report_id)
        db.commit()

        print("\n=== Test 03: Complete Report Flow - PASSED ===")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_04_report_rejection_flow(self, agent, test_patient, db):
        """Test rejecting a report"""
        print("\n=== Test 04: Report Rejection Flow ===")

        conversation_id = f"test_reject_{uuid.uuid4().hex[:12]}"
        patient_id = test_patient.patient_id

        # Create a report directly (simulating generated report)
        report_data = ReportCreate(
            patient_id=patient_id,
            conversation_id=conversation_id,
            summary="Test summary for rejection",
            key_findings="Test findings",
            recommendations="Test recommendations",
            follow_up="Test follow-up"
        )
        report = report_crud.create(db, report_data)
        db.commit()

        # Reject the report
        rejection = ReportApproval(approved=False, notes="Needs revision - missing details")
        rejected_report = report_crud.approve(db, report.report_id, rejection)
        db.commit()

        assert rejected_report.status == "rejected"
        assert rejected_report.approved_at is None

        # Verify it's NOT loaded in PatientContext
        context_builder = PatientContextBuilder()
        patient_context = context_builder.build(db, patient_id)

        for key in patient_context.patient_text_records.keys():
            if "historical_report" in key:
                pytest.fail("Rejected report should not appear in PatientContext")

        # Cleanup
        report_crud.delete(db, report.report_id)
        db.commit()

        print("=== Test 04: Report Rejection Flow - PASSED ===")

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_05_multiple_reports_for_patient(self, agent, test_patient, db):
        """Test patient with multiple approved reports"""
        print("\n=== Test 05: Multiple Reports for Patient ===")

        patient_id = test_patient.patient_id

        # Create multiple approved reports
        report_ids = []
        for i in range(3):
            conversation_id = f"test_multi_{i}_{uuid.uuid4().hex[:8]}"
            report_data = ReportCreate(
                patient_id=patient_id,
                conversation_id=conversation_id,
                summary=f"Consultation {i+1} summary",
                key_findings=f"Findings from visit {i+1}",
                recommendations=f"Recommendations {i+1}",
                follow_up="Follow-up in 2 weeks"
            )
            report = report_crud.create(db, report_data)
            report_crud.approve(db, report.report_id, ReportApproval(approved=True))
            report_ids.append(report.report_id)

        db.commit()

        # Verify all are loaded in PatientContext
        context_builder = PatientContextBuilder()
        patient_context = context_builder.build(db, patient_id)

        historical_count = sum(1 for k in patient_context.patient_text_records.keys()
                              if "historical_report" in k)

        assert historical_count == 3, f"Expected 3 historical reports, found {historical_count}"
        print(f"Found {historical_count} historical reports in PatientContext")

        # Cleanup
        for report_id in report_ids:
            report_crud.delete(db, report_id)
        db.commit()

        print("=== Test 05: Multiple Reports - PASSED ===")


class TestReportGenerationWithRealLLM:
    """Tests for report generation with real LLM"""

    @pytest.fixture(scope="class")
    def agent(self):
        """Initialize MainAgent"""
        return MainAgent()

    @pytest.mark.asyncio
    @pytest.mark.integration
    async def test_generate_structured_report(self, agent):
        """Test generating a structured report with real LLM"""
        print("\n=== Test: Generate Structured Report ===")

        from backend.agents.main_agent import tools

        # Simulate collected patient data
        state = {
            "conversation_id": f"test_report_gen_{uuid.uuid4().hex[:8]}",
            "patient_id": "test_patient",
            "messages": [],
            "accomplish": True
        }

        # Generate report
        result = await tools.generate_diagnostic_report_node(state)

        print(f"Result keys: {list(result.keys())}")

        if "report" in result:
            report = result["report"]
            print(f"Report: {report}")

            # Verify structure
            assert report is not None
            if isinstance(report, dict):
                print(f"Report keys: {list(report.keys())}")

        print("=== Test: Generate Structured Report - PASSED ===")


# Manual test function
async def manual_test_report_flow():
    """
    Manual test function for interactive testing.

    Run with:
        uv run python -c "import asyncio; from tests.integration.test_report_flow_real import manual_test_report_flow; asyncio.run(manual_test_report_flow())"
    """
    print("\n" + "="*60)
    print("MANUAL REPORT FLOW TEST")
    print("="*60)

    # Initialize
    print("\n[Init] Initializing components...")
    agent = MainAgent()
    db = SessionLocal()

    # Create test patient
    print("\n[Setup] Creating test patient...")
    patient_data = PatientCreate(
        name="Manual Test Patient",
        age=50,
        gender="female",
        phone="13900000000"
    )
    patient = patient_crud.create(db, patient_data)
    db.commit()
    print(f"Created patient: {patient.patient_id}")

    # Start conversation
    conversation_id = f"manual_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    print(f"\n[1] Starting conversation: {conversation_id}")
    first_message = await agent.astart_conversation(
        conversation_id=conversation_id,
        patient_id=patient.patient_id,
        target="Hypertension diagnosis"
    )
    print(f"AI: {first_message}")

    # Interactive loop
    print("\n[Chat] Starting chat loop (type 'quit' to end, 'done' when satisfied)")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() == 'quit':
            break
        if user_input.lower() == 'done':
            print("\nProceeding to report generation...")
            break

        response, accomplish, report = await agent.aprocess_message(
            conversation_id=conversation_id,
            user_message=user_input
        )
        print(f"AI: {response}")
        print(f"[Status: accomplish={accomplish}]")

        if accomplish and report:
            print("\n*** Report Generated! ***")
            print(f"Report: {report}")

            # Save and approve
            report_data = ReportCreate(
                patient_id=patient.patient_id,
                conversation_id=conversation_id,
                summary=report.get("summary", ""),
                key_findings=report.get("key_findings", ""),
                recommendations=report.get("recommendations", ""),
                follow_up=report.get("follow_up", ""),
                full_report=str(report)
            )
            created = report_crud.create(db, report_data)
            report_crud.approve(db, created.report_id, ReportApproval(approved=True))
            db.commit()
            print(f"Report saved and approved: {created.report_id}")
            break

    # Verify PatientContext
    print("\n[Verify] Checking PatientContext...")
    context_builder = PatientContextBuilder()
    context = context_builder.build(db, patient.patient_id)
    print(f"PatientContext text records: {list(context.patient_text_records.keys())}")

    # Cleanup
    print("\n[Cleanup] Removing test data...")
    agent.entity_graph_manager.invalidate(conversation_id)
    patient_crud.delete(db, patient.patient_id)
    db.commit()
    db.close()

    print("\n" + "="*60)
    print("MANUAL TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    asyncio.run(manual_test_report_flow())