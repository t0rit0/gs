"""
Tests for Medication Card Service

TDD Implementation - MedicationCardService
"""
import pytest
from datetime import datetime, date, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import MedicationCard, MedicationSchedule, Patient, Doctor
from backend.services.medication_card_service import MedicationCardService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_medication_service.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test patient
    patient = Patient(
        patient_id="test-patient-123",
        name="Test Patient",
        age=45,
        gender="male"
    )
    db.add(patient)
    
    # Create test doctor
    doctor = Doctor(
        doctor_id="test-doctor-456",
        name="Test Doctor",
        title="主治医师"
    )
    db.add(doctor)
    
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)


class TestMedicationCardService:
    """Tests for MedicationCardService"""
    
    def test_create_card(self, db_session):
        """Test creating a medication card"""
        # Arrange
        service = MedicationCardService(db_session)
        
        sig = {
            "dose": 0.5,
            "dose_unit": "g",
            "route": "口服",
            "frequency": "一天三次",
            "duration_days": 5
        }
        
        # Act
        card = service.create_card(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            drug_name="阿莫西林胶囊",
            sig=sig,
            instructions="饭后服用"
        )
        
        # Assert
        assert card.card_id is not None
        assert card.drug_name == "阿莫西林胶囊"
        assert card.sig["dose"] == 0.5
        assert card.status == "active"
        assert card.end_date is not None  # Auto-calculated from duration_days
    
    def test_create_card_with_custom_dates(self, db_session):
        """Test creating a card with custom prescribed and start dates"""
        # Arrange
        service = MedicationCardService(db_session)
        
        sig = {"dose": 0.5, "frequency": "一天一次"}
        prescribed_date = date(2026, 3, 1)
        start_date = date(2026, 3, 5)
        
        # Act
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="测试药品",
            sig=sig,
            prescribed_date=prescribed_date,
            start_date=start_date
        )
        
        # Assert
        assert card.prescribed_date == prescribed_date
        assert card.start_date == start_date
    
    def test_get_patient_cards(self, db_session):
        """Test getting all cards for a patient"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card1 = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"}
        )
        
        card2 = service.create_card(
            patient_id="test-patient-123",
            drug_name="布洛芬",
            sig={"dose": 200, "frequency": "按需服用"}
        )
        
        # Act - Get all cards
        all_cards = service.get_patient_cards("test-patient-123", status="all")
        
        # Assert
        assert len(all_cards) == 2
        
        # Act - Get only active cards
        active_cards = service.get_patient_cards("test-patient-123", status="active")
        
        # Assert
        assert len(active_cards) == 2
    
    def test_get_card(self, db_session):
        """Test getting a single card by ID"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"}
        )
        
        # Act
        retrieved = service.get_card(card.card_id)
        
        # Assert
        assert retrieved is not None
        assert retrieved.card_id == card.card_id
        assert retrieved.drug_name == "阿莫西林胶囊"
    
    def test_get_card_not_found(self, db_session):
        """Test getting a non-existent card"""
        # Arrange
        service = MedicationCardService(db_session)
        
        # Act
        card = service.get_card("non-existent-id")
        
        # Assert
        assert card is None
    
    def test_update_card(self, db_session):
        """Test updating a medication card"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            instructions="饭前服用"
        )
        
        # Act
        updated = service.update_card(card.card_id, {
            "instructions": "饭后服用",
            "sig": {"dose": 1.0, "frequency": "一天两次"}
        })
        
        # Assert
        assert updated is not None
        assert updated.instructions == "饭后服用"
        assert updated.sig["dose"] == 1.0
        assert updated.sig["frequency"] == "一天两次"
    
    def test_update_card_not_found(self, db_session):
        """Test updating a non-existent card"""
        # Arrange
        service = MedicationCardService(db_session)
        
        # Act
        updated = service.update_card("non-existent-id", {"instructions": "test"})
        
        # Assert
        assert updated is None
    
    def test_complete_card(self, db_session):
        """Test marking a card as completed"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次", "duration_days": 5}
        )
        
        # Act
        completed = service.complete_card(card.card_id)
        
        # Assert
        assert completed is not None
        assert completed.status == "completed"
        assert completed.end_date is not None
    
    def test_discontinue_card(self, db_session):
        """Test discontinuing a medication card"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"}
        )
        
        # Act
        discontinued = service.discontinue_card(card.card_id, reason="副作用")
        
        # Assert
        assert discontinued is not None
        assert discontinued.status == "discontinued"
        assert "副作用" in discontinued.instructions
    
    def test_import_cards_from_csv(self, db_session):
        """Test importing cards from CSV data"""
        # Arrange
        service = MedicationCardService(db_session)
        
        csv_data = [
            {
                "drug_name": "阿莫西林胶囊",
                "dose": 0.5,
                "dose_unit": "g",
                "frequency": "一天三次",
                "duration_days": 5,
                "instructions": "饭后服用"
            },
            {
                "drug_name": "布洛芬",
                "dose": 200,
                "frequency": "按需服用"
            }
        ]
        
        # Act
        result = service.import_cards_from_csv(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            csv_data=csv_data
        )
        
        # Assert
        assert result["imported"] == 2
        assert result["skipped"] == 0
        assert len(result["errors"]) == 0
        
        # Verify cards were created
        cards = service.get_patient_cards("test-patient-123")
        assert len(cards) == 2
    
    def test_import_cards_with_errors(self, db_session):
        """Test importing cards with invalid data"""
        # Arrange
        service = MedicationCardService(db_session)
        
        csv_data = [
            {
                "drug_name": "阿莫西林胶囊",
                "dose": 0.5,
                "frequency": "一天三次"
            },
            {
                # Missing required field
                "drug_name": "布洛芬"
            }
        ]
        
        # Act
        result = service.import_cards_from_csv(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            csv_data=csv_data
        )
        
        # Assert
        assert result["imported"] == 1
        assert result["skipped"] == 1
        assert len(result["errors"]) == 1
    
    def test_export_cards_to_csv(self, db_session):
        """Test exporting cards to CSV format"""
        # Arrange
        service = MedicationCardService(db_session)
        
        card = service.create_card(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={
                "dose": 0.5,
                "dose_unit": "g",
                "frequency": "一天三次",
                "duration_days": 5
            },
            instructions="饭后服用"
        )
        
        # Act
        exported = service.export_cards_to_csv("test-patient-123")
        
        # Assert
        assert len(exported) == 1
        assert exported[0]["drug_name"] == "阿莫西林胶囊"
        assert exported[0]["dose"] == 0.5
        assert exported[0]["frequency"] == "一天三次"
