"""
Tests for Patient Symptom CRUD Operations

Tests the symptom management functionality in PatientCRUD.
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from backend.database.base import SessionLocal, init_database
from backend.database.models import Patient
from backend.database.crud import PatientCRUD


@pytest.fixture
def db() -> Session:
    """Create a test database session"""
    init_database()
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def test_patient(db: Session) -> Patient:
    """Create a test patient"""
    patient_data = {
        "name": "Test Patient",
        "age": 45,
        "gender": "male"
    }
    from backend.database.schemas import PatientCreate
    patient = PatientCRUD.create(db, PatientCreate(**patient_data))
    yield patient
    # Cleanup
    PatientCRUD.delete(db, patient.patient_id)


class TestPatientSymptomCRUD:
    """Tests for patient symptom CRUD operations"""
    
    def test_add_symptom_to_patient(self, db: Session, test_patient: Patient):
        """Test adding a symptom to a patient"""
        # Add symptom
        patient = PatientCRUD.add_symptom(
            db,
            patient_id=test_patient.patient_id,
            symptom="头痛",
            description="持续性钝痛",
            status="active",
            source="manual"
        )
        
        assert patient is not None
        assert patient.symptoms is not None
        assert len(patient.symptoms) == 1
        
        symptom = patient.symptoms[0]
        assert symptom["symptom"] == "头痛"
        assert symptom["description"] == "持续性钝痛"
        assert symptom["status"] == "active"
        assert symptom["source"] == "manual"
        assert "timestamp" in symptom
    
    def test_add_multiple_symptoms(self, db: Session, test_patient: Patient):
        """Test adding multiple symptoms to a patient"""
        # Add first symptom
        PatientCRUD.add_symptom(
            db,
            patient_id=test_patient.patient_id,
            symptom="头痛",
            description="持续性钝痛",
            status="active",
            source="manual"
        )
        
        # Add second symptom
        PatientCRUD.add_symptom(
            db,
            patient_id=test_patient.patient_id,
            symptom="腹痛",
            description="饭后加重",
            status="active",
            source="manual"
        )
        
        # Add third symptom
        PatientCRUD.add_symptom(
            db,
            patient_id=test_patient.patient_id,
            symptom="头晕",
            description="",
            status="chronic",
            source="conversation"
        )
        
        # Refresh patient
        patient = PatientCRUD.get(db, test_patient.patient_id)
        
        assert len(patient.symptoms) == 3
        symptom_names = [s["symptom"] for s in patient.symptoms]
        assert "头痛" in symptom_names
        assert "腹痛" in symptom_names
        assert "头晕" in symptom_names
    
    def test_get_symptoms_returns_all(self, db: Session, test_patient: Patient):
        """Test getting all symptoms for a patient"""
        # Add symptoms
        PatientCRUD.add_symptom(db, test_patient.patient_id, "头痛", "desc1", "active", "manual")
        PatientCRUD.add_symptom(db, test_patient.patient_id, "腹痛", "desc2", "active", "manual")
        
        # Get symptoms
        symptoms = PatientCRUD.get_symptoms(db, test_patient.patient_id)
        
        assert len(symptoms) == 2
    
    def test_get_symptoms_with_time_range(self, db: Session, test_patient: Patient):
        """Test getting symptoms within a time range"""
        now = datetime.now()
        yesterday = now - timedelta(days=1)
        two_days_ago = now - timedelta(days=2)
        
        # Add symptom 1 (now)
        PatientCRUD.add_symptom(db, test_patient.patient_id, "头痛", "desc1", "active", "manual")
        
        # Manually add symptom with old timestamp
        patient = PatientCRUD.get(db, test_patient.patient_id)
        old_symptom = {
            "timestamp": two_days_ago.isoformat(),
            "symptom": "旧症状",
            "description": "旧症状描述",
            "status": "resolved",
            "source": "manual"
        }
        if patient.symptoms is None:
            patient.symptoms = []
        patient.symptoms.append(old_symptom)
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(patient, "symptoms")
        db.commit()
        
        # Get symptoms from yesterday onwards
        symptoms = PatientCRUD.get_symptoms(
            db, 
            test_patient.patient_id,
            start_time=yesterday
        )
        
        assert len(symptoms) == 1
        assert symptoms[0]["symptom"] == "头痛"
    
    def test_get_symptoms_with_end_time(self, db: Session, test_patient: Patient):
        """Test getting symptoms with end time filter"""
        now = datetime.now()
        tomorrow = now + timedelta(days=1)
        
        # Add symptom
        PatientCRUD.add_symptom(db, test_patient.patient_id, "头痛", "desc", "active", "manual")
        
        # Get symptoms up to tomorrow (should include the symptom)
        symptoms = PatientCRUD.get_symptoms(
            db,
            test_patient.patient_id,
            end_time=tomorrow
        )
        
        assert len(symptoms) == 1
        
        # Get symptoms up to 1 hour ago (should not include)
        symptoms = PatientCRUD.get_symptoms(
            db,
            test_patient.patient_id,
            end_time=now - timedelta(hours=1)
        )
        
        assert len(symptoms) == 0
    
    def test_get_symptoms_with_status_filter(self, db: Session, test_patient: Patient):
        """Test getting symptoms filtered by status"""
        # Add symptoms with different statuses
        PatientCRUD.add_symptom(db, test_patient.patient_id, "头痛", "desc1", "active", "manual")
        PatientCRUD.add_symptom(db, test_patient.patient_id, "旧病", "desc2", "chronic", "manual")
        PatientCRUD.add_symptom(db, test_patient.patient_id, "已缓解", "desc3", "resolved", "manual")
        
        # Get only active symptoms
        active_symptoms = PatientCRUD.get_symptoms(
            db,
            test_patient.patient_id,
            status="active"
        )
        
        assert len(active_symptoms) == 1
        assert active_symptoms[0]["symptom"] == "头痛"
        
        # Get only chronic symptoms
        chronic_symptoms = PatientCRUD.get_symptoms(
            db,
            test_patient.patient_id,
            status="chronic"
        )
        
        assert len(chronic_symptoms) == 1
        assert chronic_symptoms[0]["symptom"] == "旧病"
    
    def test_get_symptoms_sorted_by_time_desc(self, db: Session, test_patient: Patient):
        """Test that symptoms are sorted by timestamp descending"""
        # Add symptoms at different times
        now = datetime.now()
        
        PatientCRUD.add_symptom(db, test_patient.patient_id, "症状 1", "desc1", "active", "manual")
        
        # Manually add old symptom
        patient = PatientCRUD.get(db, test_patient.patient_id)
        old_symptom = {
            "timestamp": (now - timedelta(days=1)).isoformat(),
            "symptom": "旧症状",
            "description": "desc",
            "status": "resolved",
            "source": "manual"
        }
        if patient.symptoms is None:
            patient.symptoms = []
        patient.symptoms.insert(0, old_symptom)  # Insert at beginning
        from sqlalchemy.orm.attributes import flag_modified
        flag_modified(patient, "symptoms")
        db.commit()
        
        # Get symptoms
        symptoms = PatientCRUD.get_symptoms(db, test_patient.patient_id)
        
        # Should be sorted by time descending (newest first)
        assert len(symptoms) == 2
        assert symptoms[0]["symptom"] == "症状 1"  # Newer one first
        assert symptoms[1]["symptom"] == "旧症状"
    
    def test_update_symptom_status(self, db: Session, test_patient: Patient):
        """Test updating a symptom's status"""
        # Add symptom
        PatientCRUD.add_symptom(
            db,
            test_patient.patient_id,
            symptom="头痛",
            description="desc",
            status="active",
            source="manual"
        )
        
        # Update status
        patient = PatientCRUD.update_symptom_status(
            db,
            test_patient.patient_id,
            symptom="头痛",
            status="resolved"
        )
        
        assert patient is not None
        assert len(patient.symptoms) == 1
        assert patient.symptoms[0]["status"] == "resolved"
    
    def test_update_nonexistent_symptom_returns_patient(self, db: Session, test_patient: Patient):
        """Test updating a symptom that doesn't exist"""
        # Add a symptom
        PatientCRUD.add_symptom(db, test_patient.patient_id, "头痛", "desc", "active", "manual")
        
        # Try to update different symptom
        patient = PatientCRUD.update_symptom_status(
            db,
            test_patient.patient_id,
            symptom="不存在的症状",
            status="resolved"
        )
        
        # Should return patient but not modify anything
        assert patient is not None
        assert len(patient.symptoms) == 1
        assert patient.symptoms[0]["status"] == "active"  # Unchanged
    
    def test_add_symptom_to_nonexistent_patient_returns_none(self, db: Session):
        """Test adding symptom to a patient that doesn't exist"""
        result = PatientCRUD.add_symptom(
            db,
            patient_id="nonexistent-id",
            symptom="头痛",
            description="desc",
            status="active",
            source="manual"
        )
        
        assert result is None
    
    def test_get_symptoms_from_patient_with_no_symptoms(
        self, db: Session, test_patient: Patient
    ):
        """Test getting symptoms from a patient with no symptoms"""
        symptoms = PatientCRUD.get_symptoms(db, test_patient.patient_id)
        
        assert symptoms == []
    
    def test_get_symptoms_from_nonexistent_patient(self, db: Session):
        """Test getting symptoms from a patient that doesn't exist"""
        symptoms = PatientCRUD.get_symptoms(db, "nonexistent-id")
        
        assert symptoms == []
    
    def test_add_symptom_default_values(self, db: Session, test_patient: Patient):
        """Test adding symptom with default values"""
        patient = PatientCRUD.add_symptom(
            db,
            patient_id=test_patient.patient_id,
            symptom="头痛"
            # description, status, source use defaults
        )
        
        assert patient is not None
        symptom = patient.symptoms[0]
        assert symptom["description"] is None
        assert symptom["status"] == "active"
        assert symptom["source"] == "manual"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
