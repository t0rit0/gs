#!/usr/bin/env python
"""
Interactive test script for MainAgent with REAL LLM API

Usage:
    uv run python test_agent_interactive.py

This script tests MainAgent with:
- Real LLM API calls (using your configured model)
- Real EntityGraph (if available)
- Real database operations with sandbox
- Interactive conversation flow

Make sure your config.yaml has valid API credentials configured.
"""

import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

from backend.agents.main_agent import MainAgent
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate


async def test_conversation():
    """Interactive conversation test with REAL LLM API"""

    print("=" * 70)
    print("MainAgent Interactive Test (REAL LLM API)")
    print("=" * 70)
    print("\n⚠️  This will use your REAL LLM API configured in config.yaml")
    print("⚠️  Make sure your API keys and base URL are correctly configured\n")

    # Initialize agent (uses REAL LLM from config.yaml)
    print("[1/4] Initializing MainAgent with REAL LLM...")
    try:
        agent = MainAgent()
        print(f"✓ Agent initialized with model: {agent.config.get_model()}")
    except Exception as e:
        print(f"✗ Failed to initialize agent: {e}")
        print("\nPlease check your config.yaml for:")
        print("  - Correct API key")
        print("  - Correct base URL")
        print("  - Correct model name")
        return

    # Setup or create test patient
    print("\n[2/4] Setting up test patient...")
    db = SessionLocal()
    try:
        # Use an existing patient or create a new one
        patient = patient_crud.get(db, "test_patient_1")
        if not patient:
            patient_data = PatientCreate(
                patient_id="test_patient_1",
                name="Test Patient",
                age=45,
                gender="male",
                contact_info="test@example.com"
            )
            patient = patient_crud.create(db, patient_data)
            db.commit()
            print(f"✓ Created test patient: {patient.patient_id} (age: {patient.age})")
        else:
            print(f"✓ Using existing patient: {patient.patient_id} (age: {patient.age})")
        patient_id = patient.patient_id
    finally:
        db.close()

    # Start conversation with REAL EntityGraph and LLM
    print("\n[3/4] Starting conversation with REAL EntityGraph and LLM...")
    conversation_id = f"test_real_{patient_id}"
    try:
        first_message = await agent.astart_conversation(
            conversation_id=conversation_id,
            patient_id=patient_id,
            target="Hypertension diagnosis"
        )
        print(f"✓ Conversation started")
        print(f"\n🤖 Assistant: {first_message}")
    except Exception as e:
        print(f"✗ Failed to start conversation: {e}")
        import traceback
        traceback.print_exc()
        return

    # Interactive loop
    print("\n[4/4] Interactive conversation")
    print("Type your messages to the assistant.")
    print("The assistant will:")
    print("  - Use REAL LLM to understand your intent")
    print("  - Use EntityGraph to manage diagnostic questions")
    print("  - Use DataManager for database queries")
    print("\nCommands:")
    print("  'quit' or 'exit' - End conversation and show pending changes")
    print("  'data' - Ask about patient data (test data_manager)")
    print("  'meds' - Quick shortcut: 'What medications am I taking?'")
    print("  'status' - Show current conversation status")
    print("-" * 70)

    message_count = 0
    max_messages = 20  # Prevent infinite loops in testing

    while message_count < max_messages:
        try:
            user_input = input("\n👤 You: ").strip()

            if not user_input:
                continue

            if user_input.lower() in ['quit', 'exit', 'q']:
                print("\nEnding conversation...")
                break

            # Special shortcuts
            if user_input.lower() == 'data':
                user_input = "What medications am I currently taking and what's my medical history?"
            elif user_input.lower() == 'meds':
                user_input = "What medications am I currently taking?"
            elif user_input.lower() == 'status':
                from langgraph.checkpoint.sqlite import MemorySaver
                config = {"configurable": {"thread_id": conversation_id}}
                try:
                    state = agent.graph.get_state(config)
                    print(f"\n📊 Conversation Status:")
                    print(f"  - Messages exchanged: {len(state.values.get('messages', []))}")
                    print(f"  - Accomplish: {state.values.get('accomplish', False)}")
                    print(f"  - Last hint: {state.values.get('last_hint', 'N/A')[:80]}...")
                except Exception as e:
                    print(f"  ⚠️  Could not get status: {e}")
                continue

            # Process message with REAL LLM
            print(f"\n⏳ Processing (using REAL LLM API)...")
            response, accomplish, report = await agent.aprocess_message(
                conversation_id=conversation_id,
                user_message=user_input
            )

            print(f"\n🤖 Assistant: {response}")
            message_count += 1

            if accomplish:
                print("\n✅ Data collection complete!")
                if report:
                    print("\n📋 Diagnostic Report Generated:")
                    print(f"  Summary: {report.get('summary', 'N/A')[:200]}...")
                break

        except KeyboardInterrupt:
            print("\n\nInterrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            import traceback
            traceback.print_exc()
            message_count += 1
            continue

    if message_count >= max_messages:
        print(f"\n⚠️  Reached maximum message limit ({max_messages}) for testing")

    # End conversation and check pending operations
    print("\n" + "=" * 70)
    print("Ending Conversation")
    print("=" * 70)

    try:
        end_message, has_pending, pending_ops, report = await agent.end_conversation(
            conversation_id=conversation_id
        )

        print(f"\n{end_message}")

        if has_pending:
            print("\n⚠️  Pending Database Changes (Sandbox):")
            for i, op in enumerate(pending_ops[:5], 1):  # Show first 5
                op_type = op.get('operation_type', 'Unknown')
                table = op.get('table_name', 'unknown')
                print(f"  {i}. {op_type.upper()} on {table}")
                details = str(op.get('details', {}))[:100]
                print(f"     Details: {details}...")

            if len(pending_ops) > 5:
                print(f"\n  ... and {len(pending_ops) - 5} more operations")

            # Ask for approval
            print("\n" + "-" * 70)
            approval = input("Approve database changes? (yes/no): ").strip().lower()
            if approval in ['yes', 'y']:
                print("\n⏳ Approving and executing changes...")
                result = agent.approve_and_execute_pending_operations(conversation_id)
                if result.get('success'):
                    print(f"✓ Changes successfully committed to database")
                else:
                    print(f"✗ Approval failed: {result.get('error', 'Unknown error')}")
            else:
                agent.reject_and_discard_all(conversation_id)
                print("✗ Changes discarded (sandbox cleared)")

        elif report:
            print("\n📋 Final Report:")
            print(f"  Summary: {report.get('summary', 'N/A')[:300]}...")
            print(f"\n  Key Findings: {report.get('key_findings', 'N/A')[:200]}...")
            print(f"\n  Recommendations: {report.get('recommendations', 'N/A')[:200]}...")

    except Exception as e:
        print(f"\n❌ Error ending conversation: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 70)
    print("Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    try:
        asyncio.run(test_conversation())
    except KeyboardInterrupt:
        print("\n\nTest interrupted by user")
        sys.exit(0)
    except Exception as e:
        print(f"\n\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
