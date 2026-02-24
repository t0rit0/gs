"""
Integration Test for MainAgent

This test verifies the complete MainAgent flow including:
1. MainAgent initialization
2. Creating a conversation
3. Processing messages (with real LLM API calls)
4. Handling pending database operations
5. Ending conversation and generating reports

REQUIRES:
- Valid LLM API credentials in config.yaml
- Running database (sqlite:///./data/demo.db)
- Patient record in database

To run:
    uv run pytest tests/integration/test_mainagent_integration.py -v -s
"""

import pytest
import asyncio
import sys
from pathlib import Path
from datetime import datetime
from typing import Dict, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.main_agent import MainAgent
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, conversation_crud
from backend.config.config_manager import get_config


class TestMainAgentIntegration:
    """Integration tests for MainAgent with real LLM API"""

    @pytest.fixture(scope="module")
    def db(self):
        """Database session"""
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    @pytest.fixture(scope="module")
    def test_patient(self, db):
        """Create or get a test patient"""
        patient = patient_crud.get(db, "test_patient_001")
        if not patient:
            from backend.database.schemas import PatientCreate
            patient_data = PatientCreate(
                patient_id="test_patient_001",
                name="Test Patient",
                age=45,
                gender="male",
                contact_info="test@example.com"
            )
            patient = patient_crud.create(db, patient_data)
            db.commit()
            print(f"Created test patient: {patient.patient_id}")
        else:
            print(f"Using existing patient: {patient.patient_id}")
        return patient

    @pytest.fixture(scope="module")
    def agent(self):
        """Initialize MainAgent"""
        print("\n=== Initializing MainAgent ===")
        agent = MainAgent()
        print(f"MainAgent graph compiled: {agent.graph is not None}")
        return agent

    @pytest.mark.asyncio
    async def test_01_agent_initialization(self, agent):
        """Test 1: Verify agent initializes correctly"""
        assert agent is not None
        assert agent.graph is not None
        assert agent.llm is not None
        assert len(agent.system_prompt) > 0
        print("✅ Test 1: Agent initialization - PASSED")

    @pytest.mark.asyncio
    async def test_02_create_conversation(self, agent, test_patient):
        """Test 2: Create a new conversation"""
        print("\n=== Test 2: Creating Conversation ===")

        conversation_id = "test_conv_mainagent_001"
        patient_id = test_patient.patient_id

        try:
            # Start conversation
            first_message = await agent.astart_conversation(
                conversation_id=conversation_id,
                patient_id=patient_id,
                target="Hypertension diagnosis"
            )

            assert first_message is not None
            assert len(first_message) > 0
            print(f"First message: {first_message[:200]}...")

            # Verify conversation was created in database
            db = SessionLocal()
            conv = conversation_crud.get(db, conversation_id)
            assert conv is not None
            assert conv.model_type == "MainAgent"
            db.close()

            print("✅ Test 2: Create conversation - PASSED")

        except Exception as e:
            pytest.fail(f"Failed to create conversation: {e}")

    @pytest.mark.asyncio
    async def test_03_send_message(self, agent):
        """Test 3: Send a message to the agent (LLM API call)"""
        print("\n=== Test 3: Sending Message (LLM API Call) ===")

        conversation_id = "test_conv_mainagent_001"

        try:
            # Send a message
            user_message = "Hello, I'm here for a hypertension checkup."
            ai_message, accomplish, report = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message=user_message
            )

            assert ai_message is not None
            assert len(ai_message) > 0
            print(f"AI Response: {ai_message[:200]}...")
            print(f"Accomplish: {accomplish}")
            print(f"Report: {report}")

            print("✅ Test 3: Send message - PASSED")

        except Exception as e:
            pytest.fail(f"Failed to send message: {e}")

    @pytest.mark.asyncio
    async def test_04_query_patient_history(self, agent, test_patient):
        """Test 4: Query patient history (via DataManagerCodeAgent)"""
        print("\n=== Test 4: Query Patient History ===")

        conversation_id = "test_conv_mainagent_001"

        try:
            # Query patient history
            user_message = "What is my age and gender according to my records?"
            ai_message, accomplish, report = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message=user_message
            )

            assert ai_message is not None
            # Should contain patient information
            print(f"AI Response: {ai_message[:200]}...")

            print("✅ Test 4: Query patient history - PASSED")

        except Exception as e:
            pytest.fail(f"Failed to query patient history: {e}")

    @pytest.mark.asyncio
    async def test_05_pending_operations(self, agent):
        """Test 5: Check pending operations (sandbox)"""
        print("\n=== Test 5: Pending Operations (Sandbox) ===")

        conversation_id = "test_conv_mainagent_001"

        try:
            # Check for pending operations
            has_pending = agent.has_pending_operations(conversation_id)
            pending_ops = agent.get_pending_operations(conversation_id)

            print(f"Has pending operations: {has_pending}")
            print(f"Pending operations count: {len(pending_ops)}")
            print(f"Pending operations: {pending_ops}")

            print("✅ Test 5: Pending operations - PASSED")

        except Exception as e:
            pytest.fail(f"Failed to check pending operations: {e}")

    @pytest.mark.asyncio
    async def test_06_end_conversation(self, agent):
        """Test 6: End conversation and get summary"""
        print("\n=== Test 6: End Conversation ===")

        conversation_id = "test_conv_mainagent_001"

        try:
            # End conversation
            message, has_pending, pending_ops, report = await agent.end_conversation(
                conversation_id=conversation_id
            )

            assert message is not None
            print(f"End message: {message[:200]}...")
            print(f"Has pending: {has_pending}")
            print(f"Report available: {report is not None}")

            print("✅ Test 6: End conversation - PASSED")

        except Exception as e:
            pytest.fail(f"Failed to end conversation: {e}")

    @pytest.mark.asyncio
    async def test_07_cleanup(self, agent, db):
        """Test 7: Cleanup test data"""
        print("\n=== Test 7: Cleanup ===")

        conversation_id = "test_conv_mainagent_001"

        try:
            # Delete test conversation
            conv = conversation_crud.get(db, conversation_id)
            if conv:
                from backend.services.conversation_service import conversation_service
                conversation_service.delete_conversation(db, conversation_id)
                print(f"Deleted test conversation: {conversation_id}")

            print("✅ Test 7: Cleanup - PASSED")

        except Exception as e:
            print(f"⚠️  Cleanup warning: {e}")

    @pytest.mark.asyncio
    async def test_99_complete_flow(self, agent, test_patient):
        """
        Complete end-to-end flow test

        This is a comprehensive test that runs through the entire
        MainAgent conversation flow with real LLM API calls.
        """
        print("\n" + "="*60)
        print("COMPLETE END-TO-END FLOW TEST")
        print("="*60)

        conversation_id = "test_conv_complete_001"
        patient_id = test_patient.patient_id

        try:
            # Step 1: Create conversation
            print("\n[Step 1] Creating conversation...")
            first_message = await agent.astart_conversation(
                conversation_id=conversation_id,
                patient_id=patient_id,
                target="Hypertension diagnosis"
            )
            print(f"✓ First message: {first_message[:150]}...")

            # Step 2: Send greeting
            print("\n[Step 2] Sending greeting...")
            response1, accomplish1, report1 = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message="Hi, I'm here for my hypertension assessment."
            )
            print(f"✓ Response: {response1[:150]}...")

            # Step 3: Ask about blood pressure
            print("\n[Step 3] Discussing blood pressure...")
            response2, accomplish2, report2 = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message="My blood pressure has been around 130/85 lately."
            )
            print(f"✓ Response: {response2[:150]}...")

            # Step 4: Check pending operations
            print("\n[Step 4] Checking for pending operations...")
            has_pending = agent.has_pending_operations(conversation_id)
            pending_ops = agent.get_pending_operations(conversation_id)
            print(f"✓ Pending operations: {len(pending_ops)}")

            # Step 5: End conversation
            print("\n[Step 5] Ending conversation...")
            end_message, has_pending_end, pending_ops_end, report_end = await agent.end_conversation(
                conversation_id=conversation_id
            )
            print(f"✓ End message: {end_message[:200]}...")
            print(f"✓ Report generated: {report_end is not None}")

            # Step 6: Cleanup
            print("\n[Step 6] Cleaning up...")
            db = SessionLocal()
            conv = conversation_crud.get(db, conversation_id)
            if conv:
                from backend.services.conversation_service import conversation_service
                conversation_service.delete_conversation(db, conversation_id)
                print(f"✓ Deleted test conversation: {conversation_id}")
            db.close()

            print("\n" + "="*60)
            print("✅ COMPLETE FLOW TEST - PASSED")
            print("="*60)

        except Exception as e:
            print(f"\n❌ COMPLETE FLOW TEST FAILED: {e}")
            import traceback
            traceback.print_exc()
            pytest.fail(f"Complete flow test failed: {e}")


# Manual test function for interactive testing
async def manual_test():
    """
    Manual test function for interactive testing.

    This can be run directly with:
        uv run python -c "import asyncio; from tests.integration.test_mainagent_integration import manual_test; asyncio.run(manual_test())"
    """
    print("\n" + "="*60)
    print("MANUAL MAINAGENT TEST")
    print("="*60)

    # Initialize agent
    print("\n[Init] Initializing MainAgent...")
    agent = MainAgent()
    print("✓ MainAgent initialized")

    # Get or create test patient
    print("\n[Setup] Setting up test patient...")
    db = SessionLocal()
    patient = patient_crud.get(db, "manual_test_patient")
    if not patient:
        from backend.database.schemas import PatientCreate
        patient_data = PatientCreate(
            patient_id="manual_test_patient",
            name="Manual Test Patient",
            age=50,
            gender="female",
            contact_info="manual@example.com"
        )
        patient = patient_crud.create(db, patient_data)
        db.commit()
        print(f"✓ Created patient: {patient.patient_id}")
    else:
        print(f"✓ Using existing patient: {patient.patient_id}")
    db.close()

    # Create conversation
    print("\n[1] Creating conversation...")
    conversation_id = f"manual_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    first_message = await agent.astart_conversation(
        conversation_id=conversation_id,
        patient_id=patient.patient_id,
        target="Hypertension diagnosis"
    )
    print(f"Conversation ID: {conversation_id}")
    print(f"First message: {first_message}")

    # Interactive chat loop
    print("\n[Chat] Starting chat loop (type 'quit' to end)...")
    while True:
        user_input = input("\nYou: ").strip()
        if user_input.lower() in ['quit', 'exit', 'bye']:
            break

        if not user_input:
            continue

        response, accomplish, report = await agent.aprocess_message(
            conversation_id=conversation_id,
            user_message=user_input
        )
        print(f"AI: {response}")
        print(f"[Status: accomplish={accomplish}, has_report={report is not None}]")

        if accomplish:
            print("\n*** Data collection complete! ***")
            if report:
                print(f"Report: {report}")
            break

    # End conversation
    print("\n[End] Ending conversation...")
    end_message, has_pending, pending_ops, report = await agent.end_conversation(
        conversation_id=conversation_id
    )
    print(f"{end_message}")

    if has_pending:
        print(f"\n[Pending Operations] Found {len(pending_ops)} pending operations:")
        for i, op in enumerate(pending_ops, 1):
            print(f"  {i}. {op}")

        approve = input("\nApprove pending operations? (yes/no): ").strip().lower()
        if approve in ['yes', 'y']:
            result = agent.approve_and_execute_pending_operations(conversation_id)
            if result.get('success'):
                print(f"✓ Executed {result.get('executed_count', 0)} operations")
            else:
                print(f"✗ Failed: {result.get('error')}")

    # Cleanup
    print("\n[Cleanup] Removing test conversation...")
    db = SessionLocal()
    from backend.services.conversation_service import conversation_service
    try:
        conversation_service.delete_conversation(db, conversation_id)
        print(f"✓ Deleted conversation: {conversation_id}")
    except:
        print(f"⚠ Could not delete conversation (may already be deleted)")
    db.close()

    print("\n" + "="*60)
    print("MANUAL TEST COMPLETE")
    print("="*60)


if __name__ == "__main__":
    # Run manual test
    asyncio.run(manual_test())
