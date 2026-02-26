#!/usr/bin/env python
"""
MainAgent Integration Test - Simple Script

This script tests the complete MainAgent flow with simulated LLM responses.

To run:
    uv run python tests/integration/test_mainagent_simple.py

Requirements:
- Running database (sqlite:///./data/demo.db)

Note: This test uses mock LLM and EntityGraph to test the agent flow
without requiring actual LLM API credentials.
"""

import asyncio
import sys
from pathlib import Path
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.messages import AIMessage

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from backend.agents.main_agent import MainAgent
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, conversation_crud
from backend.services.conversation_service import conversation_service
from backend.database.schemas import PatientCreate


def create_mock_entity_graph():
    """Return None to skip EntityGraph for testing"""
    return None


async def run_test():
    """Run the integration test"""

    print("=" * 70)
    print("MainAgent Integration Test (with Mock LLM)")
    print("=" * 70)

    # Mock LLM responses
    async def mock_llm_invoke(messages):
        """Mock LLM that returns predefined responses"""
        # Check if this is an intent analysis request
        for msg in messages:
            content = msg.content if hasattr(msg, 'content') else ""
            if 'Choose one of the following intents' in content:
                # This is intent analysis - check what the user message is
                # For a greeting like "Hello, I'm here..." return continue_conversation
                # For a health statement return diagnostic_question
                if "greeting" in content.lower() or "hello" in content.lower():
                    return AIMessage(content="continue_conversation")
                else:
                    return AIMessage(content="diagnostic_question")
            elif 'translate this into a warm, natural, conversational question' in content:
                # This is hint translation request
                return AIMessage(content="Can you tell me about your blood pressure?")
        # Default greeting
        return AIMessage(content="Hello! I'm here to help with your hypertension assessment.")

    # Step 1: Initialize MainAgent with mocks
    print("\n[1/8] Initializing MainAgent...")
    agent = None
    try:
        with patch('backend.agents.main_agent.agent.ChatOpenAI') as mock_llm_class:
            # Create mock LLM instance
            mock_llm = MagicMock()
            mock_llm.ainvoke = AsyncMock(side_effect=mock_llm_invoke)
            mock_llm_class.return_value = mock_llm

            # Patch EntityGraphManager.get_or_create to return mock EntityGraph
            with patch('backend.services.entity_graph_manager.entity_graph_manager.get_or_create', create_mock_entity_graph):
                agent = MainAgent()
                print("✓ MainAgent initialized successfully")
                print(f"  - LLM Model: {agent.config.get_model()}")
                print(f"  - Graph compiled: {agent.graph is not None}")
                print(f"  - System prompt length: {len(agent.system_prompt)} chars")
    except Exception as e:
        print(f"✗ Failed to initialize MainAgent: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 2: Setup test patient
    print("\n[2/8] Setting up test patient...")
    db = SessionLocal()
    try:
        patient = patient_crud.get(db, "integration_test_patient")
        if not patient:
            patient_data = PatientCreate(
                patient_id="integration_test_patient",
                name="Integration Test Patient",
                age=45,
                gender="male",
                contact_info="integration_test@example.com"
            )
            patient = patient_crud.create(db, patient_data)
            db.commit()
            print(f"✓ Created patient: {patient.patient_id}")
        else:
            print(f"✓ Using existing patient: {patient.patient_id}")
        patient_id = patient.patient_id
    except Exception as e:
        print(f"✗ Failed to setup patient: {e}")
        db.close()
        return False
    finally:
        db.close()

    # Step 3: Create conversation
    print("\n[3/8] Creating conversation...")
    conversation_id = f"test_integration_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    try:
        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=patient_id,
            target="Hypertension diagnosis"
        )
        print(f"✓ Conversation created: {conversation_id}")
        print(f"  First message ({len(first_message)} chars): {first_message[:150]}...")
    except Exception as e:
        print(f"✗ Failed to create conversation: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 4: Send greeting message
    print("\n[4/8] Sending greeting message...")
    try:
        response, accomplish, report = await agent.aprocess_message(
            conversation_id=conversation_id,
            user_message="Hello, I'm here for my hypertension assessment."
        )
        print(f"✓ Response received ({len(response)} chars)")
        print(f"  Response: {response[:200]}...")
        print(f"  Accomplish: {accomplish}")
    except Exception as e:
        print(f"✗ Failed to send greeting: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 5: Send health information
    print("\n[5/8] Sending health information...")
    try:
        response, accomplish, report = await agent.aprocess_message(
            conversation_id=conversation_id,
            user_message="My blood pressure has been around 130/85, and I sometimes get headaches."
        )
        print(f"✓ Response received ({len(response)} chars)")
        print(f"  Response: {response[:200]}...")
        print(f"  Accomplish: {accomplish}")
    except Exception as e:
        print(f"✗ Failed to send health info: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 6: Check pending operations
    print("\n[6/8] Checking pending database operations...")
    try:
        has_pending = agent.has_pending_operations(conversation_id)
        pending_ops = agent.get_pending_operations(conversation_id)
        print(f"✓ Pending operations: {len(pending_ops)}")
        if pending_ops:
            for i, op in enumerate(pending_ops[:3], 1):  # Show first 3
                print(f"    {i}. {op.get('operation', 'Unknown')}")
            if len(pending_ops) > 3:
                print(f"    ... and {len(pending_ops) - 3} more")
    except Exception as e:
        print(f"✗ Failed to check pending ops: {e}")
        return False

    # Step 7: End conversation
    print("\n[7/8] Ending conversation...")
    try:
        end_message, has_pending, pending_ops, report = await agent.end_conversation(
            conversation_id=conversation_id
        )
        print(f"✓ Conversation ended")
        print(f"  Has pending operations: {has_pending}")
        print(f"  Report generated: {report is not None}")
        print(f"  End message: {end_message[:200]}...")
    except Exception as e:
        print(f"✗ Failed to end conversation: {e}")
        import traceback
        traceback.print_exc()
        return False

    # Step 8: Cleanup
    print("\n[8/8] Cleaning up test data...")
    db = SessionLocal()
    try:
        conv = conversation_crud.get(db, conversation_id)
        if conv:
            conversation_service.delete_conversation(db, conversation_id)
            print(f"✓ Deleted test conversation: {conversation_id}")

        # Optionally delete test patient
        # patient = patient_crud.get(db, "integration_test_patient")
        # if patient and patient.name == "Integration Test Patient":
        #     patient_service.delete_patient(db, "integration_test_patient")
        #     print(f"✓ Deleted test patient: integration_test_patient")
    except Exception as e:
        print(f"⚠ Cleanup warning: {e}")
    finally:
        db.close()

    # Summary
    print("\n" + "=" * 70)
    print("✅ Integration Test PASSED!")
    print("=" * 70)
    print("\nSummary:")
    print("  ✓ MainAgent initialization")
    print("  ✓ Conversation creation")
    print("  ✓ Message processing (with mock LLM)")
    print("  ✓ Pending operations checking")
    print("  ✓ Conversation ending")
    print("  ✓ Cleanup")
    print("\nNote: This test used mock LLM and EntityGraph.")
    print("      The agent flow was verified without external API dependencies.")
    print("=" * 70)

    return True


def main():
    """Main entry point"""
    try:
        success = asyncio.run(run_test())
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
