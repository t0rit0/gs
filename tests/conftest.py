"""
Pytest configuration and shared fixtures

Provides database sessions and test data fixtures for all tests.
"""
import sys
from pathlib import Path
import pytest

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from backend.database.base import SessionLocal, Base, engine
from backend.database.models import Patient, Conversation, Message
from backend.database.crud import patient_crud, conversation_crud, message_crud
from backend.database.schemas import PatientCreate, ConversationCreate, MessageCreate
from backend.database.image_storage import image_storage


# ============================================
# Database Fixtures
# ============================================

@pytest.fixture(scope="session")
def db_engine():
    """
    Session-scoped database engine
    Created once and reused across all tests
    """
    yield engine


@pytest.fixture(scope="function")
def db_session():
    """
    Function-scoped database session
    Each test gets a clean session
    Transactions are rolled back after each test
    """
    # Create session
    session = SessionLocal()

    # Begin transaction for rollback
    session.begin()

    yield session

    # Rollback after test
    session.rollback()
    session.close()


@pytest.fixture(scope="function")
def clean_db(db_session):
    """
    Clean database before each test
    Deletes all existing data
    """
    # Delete all messages
    db_session.query(Message).delete()
    # Delete all conversations
    db_session.query(Conversation).delete()
    # Delete all patients
    db_session.query(Patient).delete()
    db_session.commit()

    yield db_session


# ============================================
# Test Data Fixtures
# ============================================

@pytest.fixture
def sample_patient_data():
    """Sample patient creation data"""
    return PatientCreate(
        name="测试患者",
        age=35,
        gender="male",
        phone="13800000000",
        address="测试地址"
    )


@pytest.fixture
def sample_patient_with_history():
    """Sample patient with medical history"""
    return PatientCreate(
        name="张三",
        age=45,
        gender="male",
        phone="13800138000",
        address="北京市朝阳区",
        medical_history=[
            {
                "condition": "高血压",
                "diagnosis_date": "2023-01-15T00:00:00",
                "status": "chronic",
                "notes": "确诊为原发性高血压"
            }
        ],
        allergies=[
            {
                "allergen": "青霉素",
                "severity": "severe",
                "reaction": "皮疹、呼吸困难",
                "diagnosed_date": "2020-05-10T00:00:00"
            }
        ],
        medications=[
            {
                "medication_name": "氨氯地平",
                "dosage": "5mg",
                "frequency": "每日一次",
                "start_date": "2023-01-15T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "降压药"
            }
        ],
        health_metrics=[
            {
                "metric_name": "收缩压",
                "value": 145,
                "unit": "mmHg",
                "recorded_at": "2026-01-27T09:00:00",
                "notes": "早晨测量"
            }
        ]
    )


@pytest.fixture
def patient(clean_db, sample_patient_data):
    """Create and return a test patient"""
    patient = patient_crud.create(clean_db, sample_patient_data)
    return patient


@pytest.fixture
def patient_with_history(clean_db, sample_patient_with_history):
    """Create and return a patient with medical history"""
    patient = patient_crud.create(clean_db, sample_patient_with_history)
    return patient


@pytest.fixture
def conversation(clean_db, patient):
    """Create and return a test conversation"""
    conv = conversation_crud.create(clean_db, ConversationCreate(
        patient_id=patient.patient_id,
        target="高血压诊断",
        model_type="DrHyper"
    ))
    return conv


@pytest.fixture
def sample_image(tmp_path):
    """Create a sample test image"""
    from PIL import Image

    img = Image.new('RGB', (100, 100), color='red')
    image_path = tmp_path / "test_image.jpg"
    img.save(image_path)

    return str(image_path)


# ============================================
# Pytest Configuration
# ============================================

def pytest_configure(config):
    """Configure pytest markers"""
    config.addinivalue_line(
        "markers", "unit: Unit tests"
    )
    config.addinivalue_line(
        "markers", "integration: Integration tests"
    )
    config.addinivalue_line(
        "markers", "slow: Slow-running tests"
    )


# ============================================
# Test Helpers
# ============================================

class TestHelpers:
    """Helper methods for tests"""

    @staticmethod
    def assert_patient_equals(patient, expected_data):
        """Assert patient matches expected data"""
        assert patient.name == expected_data["name"]
        assert patient.age == expected_data["age"]
        assert patient.gender == expected_data["gender"]

    @staticmethod
    def assert_conversation_equals(conv, expected_data):
        """Assert conversation matches expected data"""
        assert conv.target == expected_data["target"]
        assert conv.model_type == expected_data.get("model_type", "DrHyper")
