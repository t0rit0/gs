"""
Test Patient CRUD operations
"""
import pytest
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate, PatientUpdate
from backend.database.models import Patient


@pytest.mark.unit
class TestPatientCRUD:
    """Test patient CRUD operations"""

    def test_create_patient(self, clean_db, sample_patient_data):
        """Test creating a new patient"""
        patient = patient_crud.create(clean_db, sample_patient_data)

        assert patient is not None
        assert patient.patient_id is not None
        assert patient.name == sample_patient_data.name
        assert patient.age == sample_patient_data.age
        assert patient.gender == sample_patient_data.gender
        assert patient.phone == sample_patient_data.phone
        assert patient.address == sample_patient_data.address
        assert patient.created_at is not None
        assert patient.updated_at is not None

    def test_create_patient_with_history(self, clean_db, sample_patient_with_history):
        """Test creating a patient with medical history"""
        patient = patient_crud.create(clean_db, sample_patient_with_history)

        assert patient.medical_history is not None
        assert len(patient.medical_history) == 1
        assert patient.medical_history[0]["condition"] == "高血压"
        assert len(patient.allergies) == 1
        assert len(patient.medications) == 1
        assert len(patient.health_metrics) == 1

    def test_get_patient(self, clean_db, patient):
        """Test retrieving a patient by ID"""
        found = patient_crud.get(clean_db, patient.patient_id)

        assert found is not None
        assert found.patient_id == patient.patient_id
        assert found.name == patient.name

    def test_get_nonexistent_patient(self, clean_db):
        """Test retrieving a non-existent patient"""
        found = patient_crud.get(clean_db, "non-existent-id")

        assert found is None

    def test_get_by_name(self, clean_db, patient):
        """Test searching patients by name"""
        results = patient_crud.get_by_name(clean_db, "测试")

        assert len(results) >= 1
        assert any(p.name == "测试患者" for p in results)

    def test_list_all_patients(self, clean_db):
        """Test listing all patients with pagination"""
        # Create multiple patients
        for i in range(3):
            patient_crud.create(clean_db, PatientCreate(
                name=f"患者{i}",
                age=30 + i,
                gender="male"
            ))

        patients, total = patient_crud.list_all(clean_db, skip=0, limit=10)

        assert total >= 3
        assert len(patients) >= 3
        assert all(isinstance(p, Patient) for p in patients)

    def test_list_patients_with_search(self, clean_db):
        """Test listing patients with search filter"""
        # Create patients with specific names
        patient_crud.create(clean_db, PatientCreate(
            name="搜索测试患者",
            age=40,
            gender="male"
        ))

        patient_crud.create(clean_db, PatientCreate(
            name="其他患者",
            age=35,
            gender="female"
        ))

        # Search for "搜索"
        patients, total = patient_crud.list_all(
            clean_db, skip=0, limit=10, search="搜索"
        )

        assert total >= 1
        assert any("搜索" in p.name for p in patients)

    def test_update_patient(self, clean_db, patient):
        """Test updating patient information"""
        updated = patient_crud.update(clean_db, patient.patient_id, PatientUpdate(
            age=50,
            phone="13900000000"
        ))

        assert updated is not None
        assert updated.age == 50
        assert updated.phone == "13900000000"
        # Original fields should remain unchanged
        assert updated.name == patient.name

    def test_update_nonexistent_patient(self, clean_db):
        """Test updating a non-existent patient"""
        updated = patient_crud.update(clean_db, "non-existent-id", PatientUpdate(age=50))

        assert updated is None

    def test_add_medical_history(self, clean_db, patient):
        """Test adding medical history to a patient"""
        updated = patient_crud.add_medical_history(
            clean_db,
            patient.patient_id,
            "糖尿病",
            "chronic",
            "测试病史"
        )

        assert updated is not None
        assert updated.medical_history is not None
        assert len(updated.medical_history) >= 1
        assert any(h["condition"] == "糖尿病" for h in updated.medical_history)

    def test_add_medical_history_to_new_patient(self, clean_db, sample_patient_data):
        """Test adding history to patient with empty history"""
        patient = patient_crud.create(clean_db, sample_patient_data)

        updated = patient_crud.add_medical_history(
            clean_db,
            patient.patient_id,
            "高血压",
            "chronic"
        )

        assert updated.medical_history is not None
        assert len(updated.medical_history) == 1
        assert updated.medical_history[0]["condition"] == "高血压"

    def test_add_multiple_medical_records(self, clean_db, patient):
        """Test adding multiple medical records"""
        patient_crud.add_medical_history(clean_db, patient.patient_id, "高血压", "chronic")
        patient_crud.add_medical_history(clean_db, patient.patient_id, "糖尿病", "chronic")

        updated = patient_crud.get(clean_db, patient.patient_id)

        assert len(updated.medical_history) == 2

    def test_add_health_metric(self, clean_db, patient):
        """Test adding health metric to a patient"""
        updated = patient_crud.add_health_metric(
            clean_db,
            patient.patient_id,
            "收缩压",
            140,
            "mmHg",
            "测试指标"
        )

        assert updated is not None
        assert updated.health_metrics is not None
        assert len(updated.health_metrics) >= 1
        assert any(m["metric_name"] == "收缩压" for m in updated.health_metrics)

    def test_add_multiple_health_metrics(self, clean_db, patient):
        """Test adding multiple health metrics"""
        patient_crud.add_health_metric(clean_db, patient.patient_id, "收缩压", 140, "mmHg")
        patient_crud.add_health_metric(clean_db, patient.patient_id, "舒张压", 90, "mmHg")

        updated = patient_crud.get(clean_db, patient.patient_id)

        assert len(updated.health_metrics) == 2

    def test_delete_patient(self, clean_db, patient):
        """Test deleting a patient"""
        patient_id = patient.patient_id

        result = patient_crud.delete(clean_db, patient_id)

        assert result is True

        # Verify patient is deleted
        deleted = patient_crud.get(clean_db, patient_id)
        assert deleted is None

    def test_delete_nonexistent_patient(self, clean_db):
        """Test deleting a non-existent patient"""
        result = patient_crud.delete(clean_db, "non-existent-id")

        assert result is False

    @pytest.mark.slow
    def test_patient_pagination(self, clean_db):
        """Test patient list pagination"""
        # Create 15 patients
        for i in range(15):
            patient_crud.create(clean_db, PatientCreate(
                name=f"患者{i:03d}",
                age=30 + i,
                gender="male"
            ))

        # First page
        page1, total = patient_crud.list_all(clean_db, skip=0, limit=10)
        assert len(page1) == 10
        assert total >= 15

        # Second page
        page2, _ = patient_crud.list_all(clean_db, skip=10, limit=10)
        assert len(page2) >= 5


@pytest.mark.integration
class TestPatientRelationships:
    """Test patient relationships with other models"""

    def test_patient_has_conversations(self, clean_db, patient, conversation):
        """Test that patient can have conversations"""
        # Refresh patient from database
        from backend.database.models import Patient
        updated_patient = clean_db.query(Patient).filter(
            Patient.patient_id == patient.patient_id
        ).first()

        assert updated_patient is not None
        assert len(updated_patient.conversations) >= 1
        assert any(c.target == "高血压诊断" for c in updated_patient.conversations)
