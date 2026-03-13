"""
Tests for Trend Analysis Service

TDD Implementation - Week 7 Long-term Patient Management
"""
import pytest
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.database.base import Base
from backend.database.models import Patient
from backend.services.metric_crud import MetricCRUD
from backend.services.trend_analysis_service import TrendAnalysisService


# Test database setup
SQLALCHEMY_DATABASE_URL = "sqlite:///./test_trend_analysis.db"
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


@pytest.fixture
def bp_trend_data_increasing(db_session):
    """Create BP data showing an increasing trend"""
    # Create 10 days of BP data with increasing values
    for i in range(10):
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            value=f"{120 + i * 3}/{80 + i * 2}",  # Increasing: 120/80 → 147/98
            unit="mmHg",
            measured_at=datetime.now() - timedelta(days=9 - i)
        )
    db_session.commit()


@pytest.fixture
def bp_trend_data_stable(db_session):
    """Create BP data showing a stable trend"""
    # Create 10 days of BP data with stable values
    for i in range(10):
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            value="120/80",  # Stable
            unit="mmHg",
            measured_at=datetime.now() - timedelta(days=9 - i)
        )
    db_session.commit()


@pytest.fixture
def bp_trend_data_decreasing(db_session):
    """Create BP data showing a decreasing trend"""
    # Create 10 days of BP data with decreasing values
    for i in range(10):
        MetricCRUD.create_record(
            db=db_session,
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            value=f"{140 - i * 2}/{90 - i}",  # Decreasing: 140/90 → 122/81
            unit="mmHg",
            measured_at=datetime.now() - timedelta(days=9 - i)
        )
    db_session.commit()


class TestAnalyzeTrend:
    """Tests for trend analysis"""
    
    def test_analyze_trend_increasing(self, db_session, bp_trend_data_increasing):
        """Test trend analysis detects increasing trend"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert result is not None
        assert result.get("status") != "insufficient_data"
        assert result["trend"]["direction"] == "increasing"
        assert result["trend"]["slope"] > 0
        assert "statistics" in result
        assert result["statistics"]["data_point_count"] == 10
    
    def test_analyze_trend_stable(self, db_session, bp_trend_data_stable):
        """Test trend analysis detects stable trend"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert result is not None
        assert result["trend"]["direction"] == "stable"
        assert abs(result["trend"]["slope"]) < 0.01
    
    def test_analyze_trend_decreasing(self, db_session, bp_trend_data_decreasing):
        """Test trend analysis detects decreasing trend"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert result is not None
        assert result["trend"]["direction"] == "decreasing"
        assert result["trend"]["slope"] < 0
    
    def test_analyze_trend_insufficient_data(self, db_session):
        """Test trend analysis with insufficient data"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Create only 2 data points (minimum is 3)
        for i in range(2):
            MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Blood Pressure",
                value="120/80",
                unit="mmHg",
                measured_at=datetime.now() - timedelta(days=i)
            )
        db_session.commit()
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30,
            min_data_points=3
        )
        
        # Assert
        assert result is not None
        assert result["status"] == "insufficient_data"
    
    def test_analyze_trend_no_data(self, db_session):
        """Test trend analysis with no data"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert result is not None
        assert result["status"] == "insufficient_data"
    
    def test_analyze_trend_statistics(self, db_session, bp_trend_data_increasing):
        """Test trend analysis calculates correct statistics"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert "statistics" in result
        stats = result["statistics"]
        
        # Should have 10 data points
        assert stats["data_point_count"] == 10
        
        # Statistics should be reasonable
        assert stats["average"] > 0
        assert stats["min"] <= stats["average"]
        assert stats["max"] >= stats["average"]
        assert stats["variability"] >= 0
    
    def test_analyze_trend_time_window(self, db_session, bp_trend_data_increasing):
        """Test trend analysis respects time window"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act - analyze only last 7 days
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=7
        )
        
        # Assert
        assert result is not None
        assert result["time_window"]["days"] == 7
        # Should have fewer data points than 30-day analysis
        assert result["statistics"]["data_point_count"] <= 7
    
    def test_analyze_trend_last_value(self, db_session, bp_trend_data_increasing):
        """Test trend analysis returns last value correctly"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Act
        result = service.analyze_trend(
            patient_id="test-patient-123",
            metric_name="Blood Pressure",
            days=30
        )
        
        # Assert
        assert "last_value" in result
        assert result["last_value"] is not None
        # Last value should be the most recent (147 for systolic)
        assert result["last_value"] == 147.0
        assert "last_value_date" in result


class TestExtractValues:
    """Tests for value extraction from records"""
    
    def test_extract_values_from_composite_metric(self, db_session):
        """Test extracting values from composite metrics (BP)"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Create BP records
        for i in range(5):
            MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Blood Pressure",
                value=f"{120 + i}/{80 + i}",
                unit="mmHg",
                measured_at=datetime.now() - timedelta(days=4-i)  # Oldest first
            )
        db_session.commit()
        
        # Act
        records = MetricCRUD.get_records(db_session, patient_id="test-patient-123", metric_name="Blood Pressure")
        values, timestamps = service._extract_values(records, "Blood Pressure")
        
        # Assert
        assert len(values) == 5
        # Values are sorted by time (oldest first)
        assert values[0] == 120.0  # Oldest
        assert values[-1] == 124.0  # Newest
    
    def test_extract_values_from_numeric_metric(self, db_session):
        """Test extracting values from numeric metrics (Weight)"""
        # Arrange
        service = TrendAnalysisService(db_session)
        
        # Create Weight records
        for i in range(5):
            MetricCRUD.create_record(
                db=db_session,
                patient_id="test-patient-123",
                metric_name="Weight",
                value=70 + i,
                unit="kg",
                measured_at=datetime.now() - timedelta(days=4-i)  # Oldest first
            )
        db_session.commit()
        
        # Act
        records = MetricCRUD.get_records(db_session, patient_id="test-patient-123", metric_name="Weight")
        values, timestamps = service._extract_values(records, "Weight")
        
        # Assert
        assert len(values) == 5
        assert values[0] == 70.0  # Oldest
        assert values[-1] == 74.0  # Newest


class TestCalculateStatistics:
    """Tests for statistical calculations"""
    
    def test_calculate_statistics_basic(self, db_session):
        """Test basic statistics calculation"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = [10, 20, 30, 40, 50]
        
        # Act
        stats = service._calculate_statistics(values)
        
        # Assert
        assert stats["average"] == 30.0
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["std_dev"] > 0
    
    def test_calculate_statistics_empty(self, db_session):
        """Test statistics calculation with empty values"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = []
        
        # Act
        stats = service._calculate_statistics(values)
        
        # Assert
        assert stats["average"] == 0
        assert stats["min"] == 0
        assert stats["max"] == 0
        assert stats["std_dev"] == 0


class TestCalculateTrend:
    """Tests for trend calculation"""
    
    def test_calculate_trend_increasing(self, db_session):
        """Test trend calculation for increasing values"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = [100, 110, 120, 130, 140]
        timestamps = [datetime.now() - timedelta(days=i) for i in range(4, -1, -1)]
        
        # Act
        trend = service._calculate_trend(values, timestamps)
        
        # Assert
        assert trend["direction"] == "increasing"
        assert trend["slope"] > 0
    
    def test_calculate_trend_decreasing(self, db_session):
        """Test trend calculation for decreasing values"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = [140, 130, 120, 110, 100]
        timestamps = [datetime.now() - timedelta(days=i) for i in range(4, -1, -1)]
        
        # Act
        trend = service._calculate_trend(values, timestamps)
        
        # Assert
        assert trend["direction"] == "decreasing"
        assert trend["slope"] < 0
    
    def test_calculate_trend_stable(self, db_session):
        """Test trend calculation for stable values"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = [120, 120, 120, 120, 120]
        timestamps = [datetime.now() - timedelta(days=i) for i in range(4, -1, -1)]
        
        # Act
        trend = service._calculate_trend(values, timestamps)
        
        # Assert
        assert trend["direction"] == "stable"
        assert abs(trend["slope"]) < 0.01
    
    def test_calculate_trend_insufficient_data(self, db_session):
        """Test trend calculation with insufficient data"""
        # Arrange
        service = TrendAnalysisService(db_session)
        values = [120]
        timestamps = [datetime.now()]
        
        # Act
        trend = service._calculate_trend(values, timestamps)
        
        # Assert
        assert trend["direction"] == "insufficient_data"
        assert trend["slope"] == 0
