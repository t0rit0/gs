"""
Trend Analysis Service

Health Metrics Storage and Tracking - Week 7 Implementation

Provides:
- Trend calculation (direction, slope)
- Statistical analysis (average, min, max, variability)
"""
from typing import Dict, List, Optional, Tuple
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import numpy as np

from backend.database.models import HealthMetricRecord
from backend.services.metric_crud import MetricCRUD


class TrendAnalysisService:
    """Service for analyzing health metric trends"""
    
    def __init__(self, db: Session):
        """
        Initialize trend analysis service
        
        Args:
            db: Database session
        """
        self.db = db
    
    def analyze_trend(
        self,
        patient_id: str,
        metric_name: str,
        days: int = 30,
        min_data_points: int = 3
    ) -> Optional[Dict]:
        """
        Analyze trend for a specific metric
        
        Args:
            patient_id: Patient identifier
            metric_name: Name of metric to analyze
            days: Number of days to analyze
            min_data_points: Minimum data points required
        
        Returns:
            Trend analysis result dictionary with:
            - status: "insufficient_data" or analysis results
            - trend: direction and slope
            - statistics: average, min, max, variability
            - last_value: most recent value
        """
        # Fetch records
        start_date = datetime.now() - timedelta(days=days)
        records = MetricCRUD.get_records(
            db=self.db,
            patient_id=patient_id,
            metric_name=metric_name,
            start_date=start_date
        )
        
        if len(records) < min_data_points:
            return {
                "status": "insufficient_data",
                "data_point_count": len(records),
                "message": f"Need at least {min_data_points} data points",
                "metric_name": metric_name,
                "time_window": None,
                "trend": None,
                "statistics": None,
                "last_value": None,
                "last_value_date": None
            }
        
        # Extract values
        values, timestamps = self._extract_values(records, metric_name)
        
        if not values:
            return {"status": "no_valid_data"}
        
        # Calculate statistics
        stats = self._calculate_statistics(values)
        
        # Calculate trend
        trend = self._calculate_trend(values, timestamps)
        
        return {
            "metric_name": metric_name,
            "time_window": {
                "start_date": start_date.isoformat(),
                "end_date": datetime.now().isoformat(),
                "days": days
            },
            "trend": {
                "direction": trend["direction"],
                "slope": round(trend["slope"], 4),
                "slope_unit": f"{metric_name}/day"
            },
            "statistics": {
                "average": round(stats["average"], 2),
                "min": round(stats["min"], 2),
                "max": round(stats["max"], 2),
                "variability": round(stats["std_dev"], 2),
                "data_point_count": len(values)
            },
            "status": "success",
            "last_value": values[-1] if values else None,
            "last_value_date": timestamps[-1].isoformat() if timestamps else None
        }
    
    def _extract_values(
        self,
        records: List[HealthMetricRecord],
        metric_name: str
    ) -> Tuple[List[float], List[datetime]]:
        """
        Extract numeric values from records
        
        Args:
            records: List of HealthMetricRecord
            metric_name: Name of metric for special handling (e.g., BP)
        
        Returns:
            Tuple of (values, timestamps)
        """
        values = []
        timestamps = []
        
        for record in sorted(records, key=lambda r: r.measured_at):
            value = None
            
            # For BP, use systolic as primary value
            if record.component_1_value is not None and "blood pressure" in metric_name.lower():
                value = record.component_1_value
            elif record.value_numeric is not None:
                value = record.value_numeric
            elif record.value_json:
                if isinstance(record.value_json, dict):
                    value = record.value_json.get("value") or record.value_json.get("systolic")
            
            if value is not None:
                values.append(float(value))
                timestamps.append(record.measured_at)
        
        return values, timestamps
    
    def _calculate_statistics(self, values: List[float]) -> Dict:
        """
        Calculate statistical measures
        
        Args:
            values: List of numeric values
        
        Returns:
            Dictionary with average, min, max, std_dev
        """
        if not values:
            return {"average": 0, "min": 0, "max": 0, "std_dev": 0}
        
        return {
            "average": np.mean(values),
            "min": np.min(values),
            "max": np.max(values),
            "std_dev": np.std(values)
        }
    
    def _calculate_trend(
        self,
        values: List[float],
        timestamps: List[datetime]
    ) -> Dict:
        """
        Calculate trend direction and slope
        
        Args:
            values: List of numeric values
            timestamps: List of timestamps
        
        Returns:
            Dictionary with direction and slope
        """
        if len(values) < 2:
            return {"direction": "insufficient_data", "slope": 0}
        
        # Convert timestamps to days from start
        start = timestamps[0]
        days = [(t - start).total_seconds() / 86400 for t in timestamps]
        
        # Linear regression
        slope, _ = np.polyfit(days, values, 1)
        
        # Determine direction
        if abs(slope) < 0.01:
            direction = "stable"
        elif slope > 0:
            direction = "increasing"
        else:
            direction = "decreasing"
        
        return {"direction": direction, "slope": slope}
