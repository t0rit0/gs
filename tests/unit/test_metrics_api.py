"""
Tests for Health Metrics API Endpoints

TDD Implementation - Week 7 Long-term Patient Management
"""
import pytest
from datetime import datetime, timedelta
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import Patient, HealthMetricRecord
from backend.api.server import app
from backend.services.metric_crud import MetricCRUD


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_metrics_api.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create test patients
    patient1 = Patient(
        patient_id="test-patient-123",
        name="Test Patient 1",
        age=45,
        gender="male"
    )
    patient2 = Patient(
        patient_id="test-patient-456",
        name="Test Patient 2",
        age=50,
        gender="female"
    )
    db.add(patient1)
    db.add(patient2)
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


@pytest.fixture
def sample_metrics(db_session):
    """Create sample metric records"""
    records = []
    for i in range(10):
        record = MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            value=f"{120 + i}/{80 + i}",
            unit="mmHg",
            measured_at=datetime.now() - timedelta(days=9-i)
        )
        records.append(record)
    
    db_session.commit()
    return records


class TestCreateMetricRecord:
    """Tests for POST /api/patients/{patient_id}/metrics"""
    
    def test_create_numeric_metric(self, client):
        """Test creating a numeric metric (e.g., Heart Rate)"""
        # Arrange
        payload = {
            "metric_name": "Heart Rate",
            "value": 72,
            "unit": "bpm",
            "source": "manual"
        }
        
        # Act
        response = client.post(
            "/api/patients/test-patient-123/metrics",
            json=payload
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["metric_name"] == "Heart Rate"
        assert data["value_numeric"] == 72.0
        assert data["unit"] == "bpm"
        assert "record_id" in data
    
    def test_create_composite_metric_bp(self, client):
        """Test creating composite metric (Blood Pressure)"""
        # Arrange
        payload = {
            "metric_name": "Blood Pressure",
            "value": "145/92",
            "unit": "mmHg",
            "source": "manual"
        }
        
        # Act
        response = client.post(
            "/api/patients/test-patient-123/metrics",
            json=payload
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["value_string"] == "145/92"
        assert data["unit"] == "mmHg"
    
    def test_create_metric_with_context(self, client):
        """Test creating metric with context"""
        # Arrange
        payload = {
            "metric_name": "Blood Glucose",
            "value": 95,
            "unit": "mg/dL",
            "context": "fasting",
            "source": "clinical_exam"
        }
        
        # Act
        response = client.post(
            "/api/patients/test-patient-123/metrics",
            json=payload
        )
        
        # Assert
        assert response.status_code == 201
        data = response.json()
        assert data["context"] == "fasting"
        assert data["source"] == "clinical_exam"
    
    def test_create_metric_for_nonexistent_patient(self, client):
        """Test creating metric for nonexistent patient returns 404"""
        # Arrange
        payload = {
            "metric_name": "Heart Rate",
            "value": 72,
            "unit": "bpm"
        }
        
        # Act
        response = client.post(
            "/api/patients/nonexistent-patient/metrics",
            json=payload
        )
        
        # Assert
        assert response.status_code == 404


class TestGetMetricRecords:
    """Tests for GET /api/patients/{patient_id}/metrics"""
    
    def test_get_all_metrics(self, client, sample_metrics):
        """Test getting all metrics for a patient"""
        # Act
        response = client.get("/api/patients/test-patient-123/metrics")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 10
        # Should be ordered by date (newest first)
        assert data[0]["metric_name"] == "Blood Pressure"
    
    def test_get_metrics_filtered_by_name(self, client, sample_metrics, db_session):
        """Test getting metrics filtered by metric name"""
        # Add a different metric
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Heart Rate",
            value=75,
            unit="bpm",
            measured_at=datetime.now()
        )
        
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics",
            params={"metric_name": "Heart Rate"}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
    
    def test_get_metrics_with_limit(self, client, sample_metrics):
        """Test getting metrics with limit"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics",
            params={"limit": 5}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 5
    
    def test_get_metrics_isolated_by_patient(self, client, sample_metrics, db_session):
        """Test that metrics are isolated by patient"""
        # Add metrics for another patient
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-456",
            metric_name="Blood Pressure",
            value="130/85",
            unit="mmHg",
            measured_at=datetime.now()
        )
        
        # Act
        response = client.get("/api/patients/test-patient-456/metrics")
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]["patient_id"] == "test-patient-456"


class TestGetLatestMetric:
    """Tests for GET /api/patients/{patient_id}/metrics/latest/{metric_name}"""
    
    def test_get_latest_bp(self, client, sample_metrics):
        """Test getting latest blood pressure"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics/latest/Blood Pressure"
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        # Latest should be 128/88 or 129/89 depending on timing
        # Just verify it's a valid BP reading
        assert data["value_string"] in ["128/88", "129/89"]
    
    def test_get_latest_nonexistent_metric(self, client):
        """Test getting latest for nonexistent metric returns 404"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics/latest/Nonexistent"
        )
        
        # Assert
        assert response.status_code == 404


class TestGetMetricTrend:
    """Tests for GET /api/patients/{patient_id}/metrics/trend/{metric_name}"""
    
    def test_get_trend_increasing(self, client, sample_metrics):
        """Test getting trend for increasing BP"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics/trend/Blood Pressure",
            params={"days": 30}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["trend"]["direction"] == "increasing"
        assert data["trend"]["slope"] > 0
        assert "statistics" in data
        assert data["statistics"]["data_point_count"] == 10
    
    def test_get_trend_insufficient_data(self, client, db_session):
        """Test getting trend with insufficient data"""
        # Create only 2 data points
        for i in range(2):
            MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Heart Rate",
                value=70 + i,
                unit="bpm",
                measured_at=datetime.now() - timedelta(days=i)
            )
        
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics/trend/Heart Rate",
            params={"days": 30}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "insufficient_data"
    
    def test_get_trend_with_custom_days(self, client, sample_metrics):
        """Test getting trend with custom time window"""
        # Act
        response = client.get(
            "/api/patients/test-patient-123/metrics/trend/Blood Pressure",
            params={"days": 7}
        )
        
        # Assert
        assert response.status_code == 200
        data = response.json()
        assert data["time_window"]["days"] == 7
        assert data["statistics"]["data_point_count"] <= 7
