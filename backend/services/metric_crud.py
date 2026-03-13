"""
Metric CRUD Operations

Health Metrics Storage and Tracking - Week 7 Implementation
"""
from typing import List, Optional, Any, Dict
from datetime import datetime
from sqlalchemy.orm import Session
from backend.database.models import HealthMetricRecord


class MetricCRUD:
    """CRUD operations for health metrics"""
    
    @staticmethod
    def create_record(
        db: Session,
        patient_id: str,
        metric_name: str,
        value: Any,
        measured_at: datetime,
        unit: str = None,
        source: str = "manual",
        context: str = None,
        component_1_name: str = None,
        component_1_value: float = None,
        component_2_name: str = None,
        component_2_value: float = None
    ) -> HealthMetricRecord:
        """
        Create a new health metric record

        Handles:
        - Numeric values (weight, temperature)
        - String values (BP: "145/92")
        - Composite values (auto-parses "145/92" → systolic/diastolic)
        - Explicit component values from API

        Args:
            db: Database session
            patient_id: Patient identifier
            metric_name: Name of metric (e.g., "Blood Pressure")
            value: Metric value (number or string like "145/92")
            measured_at: When the measurement was taken
            unit: Unit of measurement
            source: Data source ("manual", "wearable", "clinical_exam")
            context: Additional context (e.g., "morning_reading", "fasting")
            component_1_name: Component 1 name (e.g., "Systolic")
            component_1_value: Component 1 value (e.g., 145)
            component_2_name: Component 2 name (e.g., "Diastolic")
            component_2_value: Component 2 value (e.g., 92)

        Returns:
            Created HealthMetricRecord
        """
        # Parse value based on type
        value_numeric = None
        value_string = None
        
        # Use explicit component values if provided, otherwise parse from value
        if component_1_name and component_1_value is not None:
            # Use provided component values
            value_string = str(value)
        elif isinstance(value, (int, float)):
            value_numeric = float(value)
            value_string = str(value)
        elif isinstance(value, str):
            value_string = value
            # Parse composite values (e.g., "145/92")
            if "/" in value:
                parts = value.split("/")
                if len(parts) == 2:
                    try:
                        component_1_name = "Component 1"
                        component_1_value = float(parts[0])
                        component_2_name = "Component 2"
                        component_2_value = float(parts[1])
                    except ValueError:
                        pass
        
        # Determine metric category
        metric_category = MetricCRUD._categorize_metric(metric_name)
        
        record = HealthMetricRecord(
            patient_id=patient_id,
            metric_name=metric_name,
            metric_category=metric_category,
            value_numeric=value_numeric,
            value_string=value_string,
            component_1_name=component_1_name,
            component_1_value=component_1_value,
            component_2_name=component_2_name,
            component_2_value=component_2_value,
            unit=unit,
            source=source,
            context=context,
            measured_at=measured_at
        )
        
        db.add(record)
        db.commit()
        db.refresh(record)
        return record
    
    @staticmethod
    def get_records(
        db: Session,
        patient_id: str,
        metric_name: str = None,
        start_date: datetime = None,
        end_date: datetime = None,
        limit: int = 100
    ) -> List[HealthMetricRecord]:
        """
        Get health metric records with filters
        
        Args:
            db: Database session
            patient_id: Patient identifier
            metric_name: Optional metric name filter
            start_date: Optional start date filter
            end_date: Optional end date filter
            limit: Maximum records to return
        
        Returns:
            List of HealthMetricRecord ordered by date (newest first)
        """
        query = db.query(HealthMetricRecord).filter(
            HealthMetricRecord.patient_id == patient_id
        )
        
        if metric_name:
            query = query.filter(HealthMetricRecord.metric_name == metric_name)
        
        if start_date:
            query = query.filter(HealthMetricRecord.measured_at >= start_date)
        
        if end_date:
            query = query.filter(HealthMetricRecord.measured_at <= end_date)
        
        query = query.order_by(HealthMetricRecord.measured_at.desc())
        query = query.limit(limit)
        
        return query.all()
    
    @staticmethod
    def get_latest_record(
        db: Session,
        patient_id: str,
        metric_name: str
    ) -> Optional[HealthMetricRecord]:
        """
        Get the most recent record for a specific metric
        
        Args:
            db: Database session
            patient_id: Patient identifier
            metric_name: Name of metric
        
        Returns:
            Most recent HealthMetricRecord or None if not found
        """
        return db.query(HealthMetricRecord).filter(
            HealthMetricRecord.patient_id == patient_id,
            HealthMetricRecord.metric_name == metric_name
        ).order_by(HealthMetricRecord.measured_at.desc()).first()
    
    @staticmethod
    def _categorize_metric(metric_name: str) -> str:
        """
        Categorize metric based on name
        
        Args:
            metric_name: Name of the metric
        
        Returns:
            Category string ("vital-signs" or "laboratory")
        """
        metric_name_lower = metric_name.lower()
        
        vital_keywords = ["blood pressure", "heart rate", "temperature", "weight", "bmi", "spo2"]
        
        if any(keyword in metric_name_lower for keyword in vital_keywords):
            return "vital-signs"
        else:
            return "laboratory"
