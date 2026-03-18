"""
Tests for Medication API Endpoints

TDD Implementation - Medication API
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import Patient, Doctor
from backend.api.server import app


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_medication_api.db"
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


@pytest.fixture
def client(db_session):
    """Create test client with database override"""
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    
    from backend.database.base import get_db
    app.dependency_overrides[get_db] = override_get_db
    
    client = TestClient(app)
    return client


class TestMedicationCardAPI:
    """Tests for Medication Card API endpoints"""
    
    def test_create_medication_card(self, client):
        """Test creating a medication card"""
        # Arrange
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {
                "dose": 0.5,
                "dose_unit": "g",
                "route": "口服",
                "frequency": "一天三次",
                "duration_days": 5
            },
            "instructions": "饭后服用"
        }
        
        # Act
        response = client.post(
            "/api/patients/test-patient-123/medications",
            json=payload
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["drug_name"] == "阿莫西林胶囊"
        assert data["sig"]["dose"] == 0.5
        assert data["sig"]["frequency"] == "一天三次"
        assert data["status"] == "active"
    
    def test_get_patient_medication_cards(self, client):
        """Test getting all medication cards for a patient"""
        # Arrange - Create a card first
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {
                "dose": 0.5,
                "frequency": "一天三次"
            }
        }
        client.post("/api/patients/test-patient-123/medications", json=payload)
        
        # Act
        response = client.get("/api/patients/test-patient-123/medications")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["drug_name"] == "阿莫西林胶囊"
    
    def test_get_single_medication_card(self, client):
        """Test getting a single medication card by ID"""
        # Arrange
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {"dose": 0.5, "frequency": "一天三次"}
        }
        create_response = client.post("/api/patients/test-patient-123/medications", json=payload)
        card_id = create_response.json()["card_id"]
        
        # Act
        response = client.get(f"/api/patients/test-patient-123/medications/{card_id}")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["card_id"] == card_id
    
    def test_update_medication_card(self, client):
        """Test updating a medication card"""
        # Arrange
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {"dose": 0.5, "frequency": "一天三次"},
            "instructions": "饭前服用"
        }
        create_response = client.post("/api/patients/test-patient-123/medications", json=payload)
        card_id = create_response.json()["card_id"]
        
        # Act
        update_payload = {"instructions": "饭后服用"}
        response = client.put(
            f"/api/patients/test-patient-123/medications/{card_id}",
            json=update_payload
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["instructions"] == "饭后服用"
    
    def test_complete_medication_card(self, client):
        """Test marking a card as completed"""
        # Arrange
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {"dose": 0.5, "frequency": "一天三次"}
        }
        create_response = client.post("/api/patients/test-patient-123/medications", json=payload)
        card_id = create_response.json()["card_id"]
        
        # Act
        response = client.post(f"/api/patients/test-patient-123/medications/{card_id}/complete")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
    
    def test_discontinue_medication_card(self, client):
        """Test discontinuing a medication card"""
        # Arrange
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {"dose": 0.5, "frequency": "一天三次"}
        }
        create_response = client.post("/api/patients/test-patient-123/medications", json=payload)
        card_id = create_response.json()["card_id"]
        
        # Act
        response = client.post(
            f"/api/patients/test-patient-123/medications/{card_id}/discontinue?reason=副作用"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "discontinued"


class TestMedicationScheduleAPI:
    """Tests for Medication Schedule API endpoints"""
    
    def test_get_today_schedules(self, client):
        """Test getting today's medication schedules"""
        # Arrange - Create a card first
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {
                "dose": 0.5,
                "frequency": "一天三次"
            }
        }
        client.post("/api/patients/test-patient-123/medications", json=payload)
        
        # Act
        response = client.get("/api/patients/test-patient-123/schedules/today")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
    
    def test_confirm_medication(self, client):
        """Test confirming medication intake"""
        # Arrange - Create a card and get schedule
        payload = {
            "drug_name": "阿莫西林胶囊",
            "sig": {"dose": 0.5, "frequency": "一天一次"}
        }
        client.post("/api/patients/test-patient-123/medications", json=payload)
        
        # Get today's schedules
        schedules_response = client.get("/api/patients/test-patient-123/schedules/today")
        schedule_id = schedules_response.json()[0]["schedule_id"]
        
        # Act
        response = client.post(
            f"/api/patients/test-patient-123/schedules/{schedule_id}/confirm"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "completed"
        assert data["taken_at"] is not None
    
    def test_get_medication_summary(self, client):
        """Test getting medication summary"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/schedules/history/summary?days=30"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert "total_schedules" in data
        assert "completed" in data
        assert "completion_rate" in data
