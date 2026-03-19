"""
Tests for Symptom API Endpoints

Tests the REST API endpoints for symptom management.
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient

from backend.api.server import app
from backend.database.base import init_database, SessionLocal
from backend.database.crud import PatientCRUD
from backend.database.schemas import PatientCreate


@pytest.fixture
def client():
    """Create test client"""
    init_database()
    return TestClient(app)


@pytest.fixture
def test_patient(client):
    """Create a test patient for API tests"""
    patient_data = {
        "name": "API Test Patient",
        "age": 45,
        "gender": "male"
    }
    response = client.post("/api/patients", json=patient_data)
    assert response.status_code == 200
    return response.json()


class TestSymptomAPI:
    """Tests for symptom API endpoints"""
    
    def test_get_symptoms_empty(self, client, test_patient):
        """Test getting symptoms from patient with no symptoms"""
        patient_id = test_patient["patient_id"]
        
        response = client.get(f"/api/patients/{patient_id}/symptoms")
        
        assert response.status_code == 200
        data = response.json()
        assert isinstance(data, list)
        assert len(data) == 0
    
    def test_add_symptom_manual(self, client, test_patient):
        """Test manually adding a symptom via API"""
        patient_id = test_patient["patient_id"]
        
        symptom_data = {
            "symptom": "头痛",
            "description": "持续性钝痛",
            "status": "active",
            "source": "manual"
        }
        
        response = client.post(
            f"/api/patients/{patient_id}/symptoms",
            json=symptom_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["symptom"] == "头痛"
        assert data["description"] == "持续性钝痛"
        assert data["status"] == "active"
        assert data["source"] == "manual"
        assert "timestamp" in data
    
    def test_add_symptom_default_status(self, client, test_patient):
        """Test adding symptom with default status"""
        patient_id = test_patient["patient_id"]
        
        symptom_data = {
            "symptom": "腹痛",
            "description": "饭后加重"
            # status and source use defaults
        }
        
        response = client.post(
            f"/api/patients/{patient_id}/symptoms",
            json=symptom_data
        )
        
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "active"
        assert data["source"] == "manual"
    
    def test_get_symptoms_after_adding(self, client, test_patient):
        """Test getting symptoms after adding some"""
        patient_id = test_patient["patient_id"]
        
        # Add symptoms
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "头痛", "description": "desc1"}
        )
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "腹痛", "description": "desc2"}
        )
        
        # Get symptoms
        response = client.get(f"/api/patients/{patient_id}/symptoms")
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2
        
        symptom_names = [s["symptom"] for s in data]
        assert "头痛" in symptom_names
        assert "腹痛" in symptom_names
    
    def test_get_symptoms_with_status_filter(self, client, test_patient):
        """Test getting symptoms filtered by status"""
        patient_id = test_patient["patient_id"]
        
        # Add symptoms with different statuses
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "头痛", "status": "active"}
        )
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "旧病", "status": "chronic"}
        )
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "已缓解", "status": "resolved"}
        )
        
        # Get only active symptoms
        response = client.get(
            f"/api/patients/{patient_id}/symptoms?status=active"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symptom"] == "头痛"
        
        # Get only chronic symptoms
        response = client.get(
            f"/api/patients/{patient_id}/symptoms?status=chronic"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["symptom"] == "旧病"
    
    def test_get_symptoms_with_time_range(self, client, test_patient):
        """Test getting symptoms with time range filter"""
        patient_id = test_patient["patient_id"]
        
        # Add symptom
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "头痛"}
        )
        
        now = datetime.now()
        tomorrow = (now + timedelta(days=1)).isoformat()
        yesterday = (now - timedelta(days=1)).isoformat()
        
        # Get symptoms from yesterday (should include the symptom)
        response = client.get(
            f"/api/patients/{patient_id}/symptoms?start_time={yesterday}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        
        # Get symptoms up to tomorrow (should include)
        response = client.get(
            f"/api/patients/{patient_id}/symptoms?end_time={tomorrow}"
        )
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
    
    def test_update_symptom_status(self, client, test_patient):
        """Test updating a symptom's status"""
        patient_id = test_patient["patient_id"]
        
        # Add symptom
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "头痛", "status": "active"}
        )
        
        # Update status
        response = client.put(
            f"/api/patients/{patient_id}/symptoms/头痛/status",
            json={"status": "resolved"}
        )
        
        assert response.status_code == 200
        data = response.json()
        assert "message" in data
        assert "resolved" in data["message"]
        
        # Verify update
        get_response = client.get(
            f"/api/patients/{patient_id}/symptoms?status=resolved"
        )
        assert len(get_response.json()) == 1
    
    def test_add_symptom_to_nonexistent_patient(self, client):
        """Test adding symptom to nonexistent patient returns 404"""
        response = client.post(
            "/api/patients/nonexistent-id/symptoms",
            json={"symptom": "头痛"}
        )
        
        assert response.status_code == 404
    
    def test_get_symptoms_from_nonexistent_patient(self, client):
        """Test getting symptoms from nonexistent patient returns 404"""
        response = client.get("/api/patients/nonexistent-id/symptoms")
        
        assert response.status_code == 404
    
    def test_add_symptom_invalid_status(self, client, test_patient):
        """Test adding symptom with invalid status returns 422"""
        patient_id = test_patient["patient_id"]
        
        symptom_data = {
            "symptom": "头痛",
            "status": "invalid_status"  # Invalid status
        }
        
        response = client.post(
            f"/api/patients/{patient_id}/symptoms",
            json=symptom_data
        )
        
        assert response.status_code == 422  # Validation error
    
    def test_update_symptom_invalid_status(self, client, test_patient):
        """Test updating symptom with invalid status returns 400"""
        patient_id = test_patient["patient_id"]
        
        # Add symptom first
        client.post(
            f"/api/patients/{patient_id}/symptoms",
            json={"symptom": "头痛"}
        )
        
        # Update with invalid status
        response = client.put(
            f"/api/patients/{patient_id}/symptoms/头痛/status",
            json={"status": "invalid_status"}
        )
        
        assert response.status_code == 400  # Bad request for invalid status


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
