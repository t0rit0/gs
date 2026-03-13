"""
Tests for Health Metrics CRUD Operations

TDD Implementation - Week 7 Long-term Patient Management
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import HealthMetricRecord, Patient
from backend.services.metric_crud import MetricCRUD


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_health_metrics.db"
engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


@pytest.fixture(scope="function")
def db_session():
    """Create a fresh database for each test"""
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    
    # Create a test patient
    patient = Patient(
        patient_id="test-patient-123",
        name="Test Patient",
        age=45,
        gender="male"
    )
    db.add(patient)
    db.commit()
    
    yield db
    
    db.close()
    Base.metadata.drop_all(bind=engine)


class TestCreateMetricRecord:
    """Tests for creating metric records"""
    
    def test_create_numeric_metric(self, db_session):
        """Test creating a numeric metric record (e.g., Heart Rate)"""
        measured_at = datetime.now()
        
        record = MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Heart Rate",
            value=72,
            unit="bpm",
            measured_at=measured_at,
            source="manual"
        )
        
        assert record.record_id is not None
        assert record.patient_id == "test-patient-123"
        assert record.metric_name == "Heart Rate"
        assert record.value_numeric == 72.0
        assert record.value_string == "72"
        assert record.unit == "bpm"
        assert record.source == "manual"
        assert record.metric_category == "vital-signs"
    
    def test_create_composite_metric_blood_pressure(self, db_session):
        """Test creating a composite metric record (Blood Pressure "145/92")"""
        measured_at = datetime.now()
        
        record = MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            value="145/92",
            unit="mmHg",
            measured_at=measured_at,
            source="manual"
        )
        
        assert record.record_id is not None
        assert record.value_string == "145/92"
        assert record.component_1_name == "Component 1"
        assert record.component_1_value == 145.0
        assert record.component_2_name == "Component 2"
        assert record.component_2_value == 92.0
        assert record.unit == "mmHg"
    
    def test_create_metric_with_context(self, db_session):
        """Test creating a metric with context (e.g., morning_reading, fasting)"""
        measured_at = datetime.now()
        
        record = MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Glucose",
            value=95,
            unit="mg/dL",
            context="fasting",
            source="clinical_exam",
            measured_at=measured_at
        )
        
        assert record.context == "fasting"
        assert record.source == "clinical_exam"
        assert record.metric_category == "laboratory"
    
    def test_create_metric_with_custom_timestamp(self, db_session):
        """Test creating a metric with a custom measurement timestamp"""
        measured_at = datetime(2024, 1, 15, 10, 30, 0)
        
        record = MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Weight",
            value=75.5,
            unit="kg",
            measured_at=measured_at
        )
        
        assert record.measured_at == measured_at


class TestGetMetricRecords:
    """Tests for retrieving metric records"""
    
    @pytest.fixture
    def sample_metrics(self, db_session):
        """Create sample metric records for testing"""
        records = []
        for i in range(10):
            record = MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Blood Pressure",
                value=f"{120 + i}/{80 + i}",
                unit="mmHg",
                measured_at=datetime.now() - timedelta(days=i)
            )
            records.append(record)
        
        # Add metrics for a different patient
        MetricCRUD.create_record(
            db=db_session,
            patient_id="other-patient-456",
            metric_name="Blood Pressure",
            value="130/85",
            unit="mmHg",
            measured_at=datetime.now()
        )
        
        db_session.commit()
        return records
    
    def test_get_all_records_for_patient(self, db_session, sample_metrics):
        """Test retrieving all records for a patient"""
        records = MetricCRUD.get_records(
            db=db_session,
            patient_id="test-patient-123"
        )
        
        assert len(records) == 10
        assert all(r.patient_id == "test-patient-123" for r in records)
    
    def test_get_records_filtered_by_metric_name(self, db_session, sample_metrics):
        """Test retrieving records filtered by metric name"""
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Heart Rate",
            value=75,
            unit="bpm",
            measured_at=datetime.now()
        )
        
        records = MetricCRUD.get_records(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Heart Rate"
        )
        
        assert len(records) == 1
        assert records[0].metric_name == "Heart Rate"
    
    def test_get_records_filtered_by_date_range(self, db_session, sample_metrics):
        """Test retrieving records within a date range"""
        start_date = datetime.now() - timedelta(days=5)
        end_date = datetime.now()
        
        records = MetricCRUD.get_records(
            db=db_session,
            patient_id="test-patient-123",
            start_date=start_date,
            end_date=end_date
        )
        
        # Days 0-5 (inclusive) = 6 records, but end_date might exclude day 0
        # So we expect 5-6 records
        assert len(records) >= 5
        assert len(records) <= 6
        assert all(r.measured_at >= start_date for r in records)
    
    def test_get_records_with_limit(self, db_session, sample_metrics):
        """Test retrieving records with a limit"""
        records = MetricCRUD.get_records(
            db=db_session,
            patient_id="test-patient-123",
            limit=5
        )
        
        assert len(records) == 5
        # Should be ordered by date (newest first)
        assert records[0].measured_at >= records[1].measured_at
    
    def test_get_records_isolated_by_patient(self, db_session, sample_metrics):
        """Test that records are isolated by patient ID"""
        records = MetricCRUD.get_records(
            db=db_session,
            patient_id="test-patient-123"
        )
        
        assert len(records) == 10
        assert all(r.patient_id == "test-patient-123" for r in records)


class TestGetLatestMetric:
    """Tests for getting the latest metric record"""
    
    @pytest.fixture
    def multiple_bp_records(self, db_session):
        """Create multiple BP records at different times"""
        for i in range(5):
            MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Blood Pressure",
                value=f"{120 + i}/{80 + i}",
                unit="mmHg",
                measured_at=datetime.now() - timedelta(days=i)
            )
        db_session.commit()
    
    def test_get_latest_returns_most_recent(self, db_session, multiple_bp_records):
        """Test that get_latest returns the most recent record"""
        latest = MetricCRUD.get_latest_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure"
        )
        
        assert latest is not None
        # Should be the record from today (i=0)
        assert latest.value_string == "120/80"
    
    def test_get_latest_returns_none_for_nonexistent_metric(self, db_session):
        """Test that get_latest returns None when no records exist"""
        latest = MetricCRUD.get_latest_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Nonexistent Metric"
        )
        
        assert latest is None
    
    def test_get_latest_returns_none_for_nonexistent_patient(self, db_session, multiple_bp_records):
        """Test that get_latest returns None for nonexistent patient"""
        latest = MetricCRUD.get_latest_record(
            db=db_session,
            patient_id="nonexistent-patient",
            metric_name="Blood Pressure"
        )
        
        assert latest is None


class TestMetricCategorization:
    """Tests for automatic metric categorization"""
    
    def test_vital_signs_categorization(self, db_session):
        """Test that vital signs are categorized correctly"""
        vital_metrics = [
            ("Blood Pressure", "120/80", "mmHg"),
            ("Heart Rate", 72, "bpm"),
            ("Weight", 75.5, "kg"),
            ("Body Temperature", 36.5, "°C")
        ]
        
        for metric_name, value, unit in vital_metrics:
            record = MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name=metric_name,
                value=value,
                unit=unit,
                measured_at=datetime.now()
            )
            assert record.metric_category == "vital-signs", f"Failed for {metric_name}"
    
    def test_laboratory_categorization(self, db_session):
        """Test that laboratory metrics are categorized correctly"""
        lab_metrics = [
            ("Blood Glucose", 95, "mg/dL"),
            ("HbA1c", 5.7, "%"),
            ("Cholesterol", 200, "mg/dL")
        ]
        
        for metric_name, value, unit in lab_metrics:
            record = MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name=metric_name,
                value=value,
                unit=unit,
                measured_at=datetime.now()
            )
            assert record.metric_category == "laboratory", f"Failed for {metric_name}"
