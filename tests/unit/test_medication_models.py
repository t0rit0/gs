"""
Tests for Medication Management Models

TDD Implementation - Medication Card & Schedule
"""
import pytest
from datetime import datetime, date, time
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import MedicationCard, MedicationSchedule, Patient, Doctor


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_medication.db"
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


class TestMedicationCardModel:
    """Tests for MedicationCard model"""
    
    def test_create_medication_card(self, db_session):
        """Test creating a medication card with SIG format"""
        # Arrange
        sig = {
            "dose": 0.5,
            "dose_unit": "g",
            "route": "口服",
            "frequency": "一天三次",
            "duration_days": 5
        }
        
        dispense = {
            "total_quantity": 2,
            "quantity_unit": "盒"
        }
        
        # Act
        card = MedicationCard(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            drug_name="阿莫西林胶囊",
            sig=sig,
            dispense=dispense,
            instructions="饭后服用",
            prescribed_date=date.today(),
            source="manual"
        )
        
        db_session.add(card)
        db_session.commit()
        db_session.refresh(card)
        
        # Assert
        assert card.card_id is not None
        assert card.drug_name == "阿莫西林胶囊"
        assert card.sig["dose"] == 0.5
        assert card.sig["frequency"] == "一天三次"
        assert card.dispense["total_quantity"] == 2
        assert card.instructions == "饭后服用"
        assert card.status == "active"
    
    def test_medication_card_end_date_calculation(self, db_session):
        """Test automatic end date calculation from duration_days"""
        # Arrange
        sig = {
            "dose": 0.5,
            "dose_unit": "g",
            "route": "口服",
            "frequency": "一天三次",
            "duration_days": 5
        }
        
        prescribed_date = date(2026, 3, 13)
        
        # Act
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig=sig,
            prescribed_date=prescribed_date
        )
        
        end_date = card.calculate_end_date()
        
        # Assert
        assert end_date == date(2026, 3, 18)  # 5 days after March 13
    
    def test_medication_card_to_dict(self, db_session):
        """Test converting card to dictionary"""
        # Arrange
        sig = {
            "dose": 0.5,
            "dose_unit": "g",
            "route": "口服",
            "frequency": "一天三次",
            "duration_days": 5
        }
        
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig=sig,
            prescribed_date=date.today()
        )
        
        db_session.add(card)
        db_session.commit()
        
        # Act
        card_dict = card.to_dict()
        
        # Assert
        assert card_dict["drug_name"] == "阿莫西林胶囊"
        assert card_dict["sig"]["dose"] == 0.5
        assert card_dict["sig"]["frequency"] == "一天三次"
        assert "card_id" in card_dict
        assert "created_at" in card_dict
    
    def test_medication_card_status_transitions(self, db_session):
        """Test medication card status transitions"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today(),
            status="active"
        )
        
        db_session.add(card)
        db_session.commit()
        
        # Act & Assert - Active to Completed
        card.status = "completed"
        card.end_date = date.today()
        db_session.commit()
        assert card.status == "completed"
        
        # Act & Assert - Active to Discontinued
        card.status = "active"
        card.end_date = None
        db_session.commit()
        
        card.status = "discontinued"
        card.end_date = date.today()
        db_session.commit()
        assert card.status == "discontinued"
    
    def test_medication_card_patient_relationship(self, db_session):
        """Test patient-card relationship"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        
        db_session.add(card)
        db_session.commit()
        
        # Act
        patient = db_session.query(Patient).filter(
            Patient.patient_id == "test-patient-123"
        ).first()
        
        # Assert
        assert len(patient.medication_cards) == 1
        assert patient.medication_cards[0].drug_name == "阿莫西林胶囊"
    
    def test_medication_card_doctor_relationship(self, db_session):
        """Test doctor-card relationship"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        
        db_session.add(card)
        db_session.commit()
        
        # Act
        doctor = db_session.query(Doctor).filter(
            Doctor.doctor_id == "test-doctor-456"
        ).first()
        
        # Assert
        assert len(doctor.medication_cards) == 1
        assert doctor.medication_cards[0].drug_name == "阿莫西林胶囊"


class TestMedicationScheduleModel:
    """Tests for MedicationSchedule model"""
    
    def test_create_medication_schedule(self, db_session):
        """Test creating a medication schedule"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        # Act
        schedule = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0),
            dose=0.5,
            dose_unit="g",
            route="口服",
            status="pending"
        )
        
        db_session.add(schedule)
        db_session.commit()
        db_session.refresh(schedule)
        
        # Assert
        assert schedule.schedule_id is not None
        assert schedule.scheduled_date == date.today()
        assert schedule.scheduled_time == time(8, 0)
        assert schedule.dose == 0.5
        assert schedule.status == "pending"
    
    def test_medication_schedule_confirm_medication(self, db_session):
        """Test confirming medication intake"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        schedule = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0),
            status="pending"
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Act
        taken_at = datetime.now()
        schedule.taken_at = taken_at
        schedule.status = "completed"
        db_session.commit()
        
        # Assert
        assert schedule.status == "completed"
        assert schedule.taken_at is not None
    
    def test_medication_schedule_to_dict(self, db_session):
        """Test converting schedule to dictionary"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        schedule = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0),
            dose=0.5,
            dose_unit="g",
            status="pending"
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Act
        schedule_dict = schedule.to_dict()
        
        # Assert
        assert schedule_dict["scheduled_date"] == date.today().isoformat()
        assert schedule_dict["scheduled_time"] == time(8, 0).isoformat()
        assert schedule_dict["dose"] == 0.5
        assert schedule_dict["status"] == "pending"
    
    def test_medication_schedule_status_values(self, db_session):
        """Test medication schedule status values"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        # Act & Assert - All status values
        valid_statuses = ["pending", "completed", "missed", "skipped"]
        
        for status in valid_statuses:
            schedule = MedicationSchedule(
                patient_id="test-patient-123",
                card_id=card.card_id,
                scheduled_date=date.today(),
                scheduled_time=time(8, 0),
                status=status
            )
            db_session.add(schedule)
            db_session.commit()
            
            assert schedule.status == status
            db_session.delete(schedule)
            db_session.commit()
    
    def test_medication_schedule_patient_relationship(self, db_session):
        """Test schedule-patient relationship"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        schedule = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0)
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Act
        patient = db_session.query(Patient).filter(
            Patient.patient_id == "test-patient-123"
        ).first()
        
        # Assert - Can access schedules through patient
        schedules = db_session.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == patient.patient_id
        ).all()
        
        assert len(schedules) == 1
        assert schedules[0].card.drug_name == "阿莫西林胶囊"  # Access through relationship
    
    def test_medication_schedule_card_relationship(self, db_session):
        """Test schedule-card relationship"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        schedule = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0)
        )
        db_session.add(schedule)
        db_session.commit()
        
        # Act
        schedule_with_card = db_session.query(MedicationSchedule).filter(
            MedicationSchedule.schedule_id == schedule.schedule_id
        ).first()
        
        # Assert
        assert schedule_with_card.card is not None
        assert schedule_with_card.card.drug_name == "阿莫西林胶囊"


class TestMedicationCardQueries:
    """Tests for MedicationCard database queries"""
    
    def test_get_patient_active_cards(self, db_session):
        """Test querying active cards for a patient"""
        # Arrange
        card1 = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today(),
            status="active"
        )
        
        card2 = MedicationCard(
            patient_id="test-patient-123",
            drug_name="布洛芬",
            sig={"dose": 200, "frequency": "按需服用"},
            prescribed_date=date.today(),
            status="completed"
        )
        
        db_session.add(card1)
        db_session.add(card2)
        db_session.commit()
        
        # Act
        active_cards = db_session.query(MedicationCard).filter(
            MedicationCard.patient_id == "test-patient-123",
            MedicationCard.status == "active"
        ).all()
        
        # Assert
        assert len(active_cards) == 1
        assert active_cards[0].drug_name == "阿莫西林胶囊"
    
    def test_get_cards_by_doctor(self, db_session):
        """Test querying cards by doctor"""
        # Arrange
        card1 = MedicationCard(
            patient_id="test-patient-123",
            doctor_id="test-doctor-456",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        
        db_session.add(card1)
        db_session.commit()
        
        # Act
        doctor_cards = db_session.query(MedicationCard).filter(
            MedicationCard.doctor_id == "test-doctor-456"
        ).all()
        
        # Assert
        assert len(doctor_cards) == 1
        assert doctor_cards[0].drug_name == "阿莫西林胶囊"
    
    def test_get_schedules_by_date(self, db_session):
        """Test querying schedules by date"""
        # Arrange
        card = MedicationCard(
            patient_id="test-patient-123",
            drug_name="阿莫西林胶囊",
            sig={"dose": 0.5, "frequency": "一天三次"},
            prescribed_date=date.today()
        )
        db_session.add(card)
        db_session.commit()
        
        schedule1 = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(8, 0)
        )
        
        schedule2 = MedicationSchedule(
            patient_id="test-patient-123",
            card_id=card.card_id,
            scheduled_date=date.today(),
            scheduled_time=time(14, 0)
        )
        
        db_session.add(schedule1)
        db_session.add(schedule2)
        db_session.commit()
        
        # Act
        today_schedules = db_session.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == "test-patient-123",
            MedicationSchedule.scheduled_date == date.today()
        ).order_by(MedicationSchedule.scheduled_time).all()
        
        # Assert
        assert len(today_schedules) == 2
        assert today_schedules[0].scheduled_time == time(8, 0)
        assert today_schedules[1].scheduled_time == time(14, 0)
