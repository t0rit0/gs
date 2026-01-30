"""
Simple database test script

Quick test to verify database functionality.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.base import SessionLocal, get_database_info
from backend.database.crud import patient_crud, conversation_crud, message_crud
from backend.database.schemas import PatientCreate, ConversationCreate, MessageCreate
from backend.database.image_storage import image_storage


def test_database_info():
    """Test database connection and info"""
    print("\n" + "="*60)
    print("Test 1: Database Information")
    print("="*60)

    info = get_database_info()
    print(f"✅ Database URL: {info['url']}")
    print(f"✅ Environment: {info['environment']}")
    print(f"✅ Driver: {info['driver']}")
    print(f"✅ Tables: {', '.join(info['tables'])}")


def test_patient_crud():
    """Test patient CRUD operations"""
    print("\n" + "="*60)
    print("Test 2: Patient CRUD Operations")
    print("="*60)

    db = SessionLocal()

    try:
        # Create
        print("\n📝 Creating patient...")
        patient_data = PatientCreate(
            name="测试患者",
            age=35,
            gender="male",
            phone="13800000000",
            address="测试地址"
        )
        patient = patient_crud.create(db, patient_data)
        print(f"✅ Patient created: {patient.name} (ID: {patient.patient_id})")

        # Read
        print("\n🔍 Reading patient...")
        found = patient_crud.get(db, patient.patient_id)
        assert found is not None
        assert found.name == "测试患者"
        print(f"✅ Patient found: {found.name}")

        # Update
        print("\n✏️  Updating patient...")
        from backend.database.schemas import PatientUpdate
        updated = patient_crud.update(db, patient.patient_id, PatientUpdate(age=36))
        assert updated.age == 36
        print(f"✅ Patient age updated: {updated.age}")

        # Add medical history
        print("\n📋 Adding medical history...")
        patient = patient_crud.add_medical_history(
            db, patient.patient_id, "高血压", "chronic", "测试病历"
        )
        assert len(patient.medical_history) == 1
        print(f"✅ Medical history added: {patient.medical_history[0]['condition']}")

        # Add health metric
        print("\n📊 Adding health metric...")
        patient = patient_crud.add_health_metric(
            db, patient.patient_id, "收缩压", 140, "mmHg"
        )
        assert len(patient.health_metrics) == 1
        print(f"✅ Health metric added: {patient.health_metrics[0]['metric_name']}")

        # List
        print("\n📋 Listing patients...")
        patients, total = patient_crud.list_all(db, limit=10)
        print(f"✅ Found {total} patient(s)")

        # Search
        print("\n🔍 Searching patients...")
        results = patient_crud.get_by_name(db, "测试")
        print(f"✅ Search returned {len(results)} result(s)")

        # Cleanup
        print("\n🗑️  Cleaning up...")
        patient_crud.delete(db, patient.patient_id)
        print(f"✅ Patient deleted")

        print("\n✅ All patient CRUD tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def test_conversation_crud():
    """Test conversation CRUD operations"""
    print("\n" + "="*60)
    print("Test 3: Conversation CRUD Operations")
    print("="*60)

    db = SessionLocal()

    try:
        # Create a patient first
        patient = patient_crud.create(db, PatientCreate(
            name="对话测试患者",
            age=40,
            gender="female"
        ))
        print(f"✅ Created patient for testing: {patient.name}")

        # Create conversation
        print("\n📝 Creating conversation...")
        conv_data = ConversationCreate(
            patient_id=patient.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        )
        conv = conversation_crud.create(db, conv_data)
        print(f"✅ Conversation created: {conv.target} (ID: {conv.conversation_id})")

        # Check DrHyper state
        assert conv.drhyper_state is not None
        assert "entity_graph" in conv.drhyper_state
        print(f"✅ DrHyper state initialized")

        # Read
        print("\n🔍 Reading conversation...")
        found = conversation_crud.get(db, conv.conversation_id)
        assert found is not None
        print(f"✅ Conversation found: {found.target}")

        # List by patient
        print("\n📋 Listing conversations by patient...")
        convs, total = conversation_crud.list_by_patient(db, patient.patient_id)
        assert total >= 1
        print(f"✅ Found {total} conversation(s)")

        # Add messages
        print("\n💬 Adding messages...")
        msg1 = message_crud.create(db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="ai",
            content="您好！请问有什么可以帮助您？"
        ))
        print(f"✅ Message 1 created: [ai] {msg1.content[:20]}...")

        msg2 = message_crud.create(db, MessageCreate(
            conversation_id=conv.conversation_id,
            role="human",
            content="我最近血压有点高"
        ))
        print(f"✅ Message 2 created: [human] {msg2.content}")

        # List messages
        print("\n📋 Listing messages...")
        messages = message_crud.list_by_conversation(db, conv.conversation_id)
        assert len(messages) == 2
        print(f"✅ Found {len(messages)} messages")

        # Close conversation
        print("\n🔚 Closing conversation...")
        closed_conv = conversation_crud.close(db, conv.conversation_id)
        assert closed_conv.status == "completed"
        print(f"✅ Conversation status: {closed_conv.status}")

        # Cleanup
        print("\n🗑️  Cleaning up...")
        conversation_crud.delete(db, conv.conversation_id)
        patient_crud.delete(db, patient.patient_id)
        print(f"✅ Test data deleted")

        print("\n✅ All conversation CRUD tests passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def test_image_storage():
    """Test image storage"""
    print("\n" + "="*60)
    print("Test 4: Image Storage")
    print("="*60)

    # Create a test image
    from PIL import Image
    import io

    print("\n📝 Creating test image...")
    img = Image.new('RGB', (100, 100), color='red')
    test_image_path = "/tmp/test_image.jpg"
    img.save(test_image_path)
    print(f"✅ Test image created: {test_image_path}")

    try:
        # Save image
        print("\n💾 Saving image...")
        paths = image_storage.save_conversation_images(
            "test-conv-123",
            1,
            [test_image_path]
        )
        print(f"✅ Image saved: {paths[0]}")

        # Get storage stats
        print("\n📊 Storage statistics...")
        stats = image_storage.get_storage_stats()
        print(f"✅ Total conversations: {stats['total_conversations']}")
        print(f"✅ Total images: {stats['total_images']}")
        print(f"✅ Total size: {stats['total_size_mb']} MB")

        # Cleanup
        print("\n🗑️  Cleaning up...")
        import os
        os.remove(test_image_path)
        image_storage.delete_conversation_images("test-conv-123")
        print(f"✅ Cleanup complete")

        print("\n✅ Image storage test passed!")

    except Exception as e:
        print(f"\n❌ Test failed: {e}")
        raise


def run_all_tests():
    """Run all database tests"""
    print("\n" + "="*60)
    print("🧪 Database Test Suite")
    print("="*60)

    try:
        test_database_info()
        test_patient_crud()
        test_conversation_crud()
        test_image_storage()

        print("\n" + "="*60)
        print("✅ All tests passed successfully!")
        print("="*60 + "\n")

    except Exception as e:
        print("\n" + "="*60)
        print(f"❌ Tests failed: {e}")
        print("="*60 + "\n")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Run database tests")
    parser.add_argument(
        "test",
        nargs="?",
        choices=["info", "patient", "conversation", "image", "all"],
        default="all",
        help="Test to run (default: all)"
    )

    args = parser.parse_args()

    if args.test == "info":
        test_database_info()
    elif args.test == "patient":
        test_patient_crud()
    elif args.test == "conversation":
        test_conversation_crud()
    elif args.test == "image":
        test_image_storage()
    else:
        run_all_tests()
