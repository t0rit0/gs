"""
Database Initialization Script

Initialize database tables and optionally populate with sample data.
"""
import sys
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from backend.database.base import init_database, reset_database, get_database_info
from backend.database.models import Patient, Conversation, Message
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud, conversation_crud, message_crud
from backend.database.schemas import PatientCreate, MessageCreate
import uuid


def create_sample_data():
    """
    Create sample patients and conversations for testing
    """
    db = SessionLocal()

    try:
        print("📝 Creating sample patients...")

        # Create sample patients
        patients_data = [
            {
                "name": "张三",
                "age": 45,
                "gender": "male",
                "phone": "13800138000",
                "address": "北京市朝阳区",
                "medical_history": [
                    {
                        "condition": "高血压",
                        "diagnosis_date": "2023-01-15T00:00:00",
                        "status": "chronic",
                        "notes": "确诊为原发性高血压"
                    }
                ],
                "allergies": [
                    {
                        "allergen": "青霉素",
                        "severity": "severe",
                        "reaction": "皮疹、呼吸困难",
                        "diagnosed_date": "2020-05-10T00:00:00"
                    }
                ],
                "medications": [
                    {
                        "medication_name": "氨氯地平",
                        "dosage": "5mg",
                        "frequency": "每日一次",
                        "start_date": "2023-01-15T00:00:00",
                        "prescribing_doctor": "李医生",
                        "notes": "降压药"
                    }
                ],
                "family_history": [
                    {
                        "relationship": "父亲",
                        "condition": "高血压",
                        "age_of_onset": 50
                    },
                    {
                        "relationship": "母亲",
                        "condition": "2型糖尿病",
                        "age_of_onset": 55
                    }
                ],
                "health_metrics": [
                    {
                        "metric_name": "收缩压",
                        "value": 145,
                        "unit": "mmHg",
                        "recorded_at": "2026-01-27T09:00:00",
                        "notes": "早晨测量"
                    },
                    {
                        "metric_name": "舒张压",
                        "value": 95,
                        "unit": "mmHg",
                        "recorded_at": "2026-01-27T09:00:00",
                        "notes": "早晨测量"
                    },
                    {
                        "metric_name": "心率",
                        "value": 78,
                        "unit": "bpm",
                        "recorded_at": "2026-01-27T09:00:00",
                        "notes": "静息心率"
                    }
                ]
            },
            {
                "name": "李四",
                "age": 38,
                "gender": "female",
                "phone": "13900139000",
                "address": "上海市浦东新区",
                "medical_history": [],
                "allergies": [],
                "medications": [],
                "family_history": [],
                "health_metrics": []
            },
            {
                "name": "王五",
                "age": 62,
                "gender": "male",
                "phone": "13700137000",
                "address": "广州市天河区",
                "medical_history": [
                    {
                        "condition": "2型糖尿病",
                        "diagnosis_date": "2020-06-20T00:00:00",
                        "status": "chronic",
                        "notes": "通过血糖检查确诊"
                    },
                    {
                        "condition": "高血脂",
                        "diagnosis_date": "2021-03-10T00:00:00",
                        "status": "chronic",
                        "notes": "体检发现"
                    }
                ],
                "allergies": [],
                "medications": [
                    {
                        "medication_name": "二甲双胍",
                        "dosage": "500mg",
                        "frequency": "每日两次",
                        "start_date": "2020-06-20T00:00:00",
                        "prescribing_doctor": "陈医生",
                        "notes": "降糖药"
                    }
                ],
                "family_history": [
                    {
                        "relationship": "母亲",
                        "condition": "2型糖尿病",
                        "age_of_onset": 60
                    }
                ],
                "health_metrics": [
                    {
                        "metric_name": "空腹血糖",
                        "value": 7.2,
                        "unit": "mmol/L",
                        "recorded_at": "2026-01-25T08:00:00",
                        "notes": "早餐前测量"
                    }
                ]
            }
        ]

        created_patients = []
        for patient_data in patients_data:
            patient = patient_crud.create(db, PatientCreate(**patient_data))
            created_patients.append(patient)
            print(f"   ✅ Created patient: {patient.name} (ID: {patient.patient_id})")

        print(f"\n📝 Creating sample conversations...")

        # Create sample conversation for first patient
        patient1 = created_patients[0]

        # Create conversation
        from backend.database.schemas import ConversationCreate
        conv = conversation_crud.create(db, ConversationCreate(
            patient_id=patient1.patient_id,
            target="高血压诊断",
            model_type="DrHyper"
        ))
        print(f"   ✅ Created conversation: {conv.target} (ID: {conv.conversation_id})")

        # Add messages
        messages = [
            {
                "role": "ai",
                "content": "您好！我是DrHyper医生助手。请问您最近有什么健康问题需要咨询吗？"
            },
            {
                "role": "human",
                "content": "我最近血压有点高，想咨询一下。"
            },
            {
                "role": "ai",
                "content": "了解。您能告诉我具体的血压数值吗？包括收缩压和舒张压。另外，这种情况持续多久了？"
            },
            {
                "role": "human",
                "content": "收缩压大概145左右，舒张压95左右。这种情况有一个多星期了。"
            }
        ]

        for i, msg_data in enumerate(messages, 1):
            msg = message_crud.create(db, MessageCreate(
                conversation_id=conv.conversation_id,
                **msg_data
            ))
            print(f"   ✅ Added message {i}: [{msg.role}] {msg.content[:30]}...")

        print(f"\n✅ Sample data created successfully!")
        print(f"\n📊 Summary:")
        print(f"   - Patients: {len(created_patients)}")
        print(f"   - Conversations: 1")
        print(f"   - Messages: 4")

        return created_patients

    except Exception as e:
        print(f"\n❌ Error creating sample data: {e}")
        db.rollback()
        raise
    finally:
        db.close()


def main():
    """
    Main function for database initialization
    """
    import argparse

    parser = argparse.ArgumentParser(
        description="Database initialization and management",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Initialize database
  python -m backend.database.init_db

  # Reset database (drop and recreate)
  python -m backend.database.init_db --reset

  # Initialize with sample data
  python -m backend.database.init_db --sample

  # Show database information
  python -m backend.database.init_db --info
        """
    )

    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset database (drop all tables and recreate)"
    )

    parser.add_argument(
        "--sample",
        action="store_true",
        help="Create sample data after initialization"
    )

    parser.add_argument(
        "--info",
        action="store_true",
        help="Show database information and exit"
    )

    args = parser.parse_args()

    # Show info if requested
    if args.info:
        info = get_database_info()
        print("\n" + "="*50)
        print("📊 Database Information")
        print("="*50)
        print(f"URL: {info['url']}")
        print(f"Environment: {info['environment']}")
        print(f"Driver: {info['driver']}")
        print(f"Tables: {', '.join(info['tables'])}")
        print("="*50 + "\n")
        return

    # Reset if requested
    if args.reset:
        confirm = input("⚠️  This will delete all data. Type 'yes' to confirm: ")
        if confirm.lower() != 'yes':
            print("❌ Cancelled")
            return
        print("\n🔄 Resetting database...")
        reset_database()
        print()

    # Initialize database
    print("🚀 Initializing database...")
    print("-" * 50)
    init_database()
    print("-" * 50)

    # Create sample data if requested
    if args.sample:
        print()
        create_sample_data()

    print("\n✅ Database initialization complete!")
    print(f"\n💡 Next steps:")
    print(f"   1. Explore the data: sqlite3 data/demo.db")
    print(f"   2. Run tests: pytest tests/database/")
    print(f"   3. Start backend: python -m backend.api.server")


if __name__ == "__main__":
    main()
