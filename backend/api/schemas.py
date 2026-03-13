"""
API Schemas for Health Metrics

Health Metrics Storage and Tracking - Week 7 Implementation
"""
from pydantic import BaseModel, Field, field_validator
from typing import Optional, Any, Dict
from datetime import datetime


class MetricRecordCreate(BaseModel):
    """Schema for creating a metric record"""
    metric_name: str = Field(..., description="Name of metric (e.g., 'Blood Pressure')")
    value: Any = Field(..., description="Metric value (number or string like '145/92')")
    unit: Optional[str] = Field(None, description="Unit of measurement")
    measured_at: Optional[datetime] = Field(default_factory=datetime.now, description="When measurement was taken")
    source: Optional[str] = Field("manual", description="Data source")
    context: Optional[str] = Field(None, description="Additional context")
    
    # Component fields for composite metrics (e.g., Blood Pressure)
    component_1_name: Optional[str] = Field(None, description="Component 1 name (e.g., 'Systolic')")
    component_1_value: Optional[float] = Field(None, description="Component 1 value (e.g., 145)")
    component_2_name: Optional[str] = Field(None, description="Component 2 name (e.g., 'Diastolic')")
    component_2_value: Optional[float] = Field(None, description="Component 2 value (e.g., 92)")


class MetricRecordResponse(BaseModel):
    """Schema for metric record response"""
    record_id: str
    patient_id: str
    metric_name: str
    metric_category: Optional[str]
    value_numeric: Optional[float]
    value_string: Optional[str]
    component_1: Optional[Dict[str, Any]] = None
    component_2: Optional[Dict[str, Any]] = None
    unit: Optional[str]
    source: str
    context: Optional[str]
    measured_at: datetime

    class Config:
        from_attributes = True
    
    @field_validator('component_1', 'component_2', mode='before')
    @classmethod
    def validate_component(cls, v):
        """Handle component validation"""
        if v is None:
            return None
        return v


class MetricTrendResponse(BaseModel):
    """Schema for trend analysis response"""
    metric_name: Optional[str]
    time_window: Optional[Dict]
    trend: Optional[Dict]
    statistics: Optional[Dict]
    status: Optional[str]
    last_value: Optional[float]
    last_value_date: Optional[str]
