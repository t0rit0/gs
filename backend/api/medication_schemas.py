"""
API Schemas for Medication Management

TDD Implementation - Medication Schemas
"""

from pydantic import BaseModel, Field, field_validator
from typing import Optional, Dict, Any, List
from datetime import date, datetime, time


# ============================================
# MedicationCard Schemas
# ============================================

class MedicationCardCreate(BaseModel):
    """创建用药卡片"""
    drug_name: str = Field(..., description="药品名称")
    generic_name: Optional[str] = Field(None, description="通用名")
    
    sig: Dict[str, Any] = Field(..., description="用药说明")
    # {"dose": 0.5, "dose_unit": "g", "route": "口服", "frequency": "一天三次", "duration_days": 5}
    
    dispense: Optional[Dict[str, Any]] = Field(None, description="配药信息")
    # {"total_quantity": 2, "quantity_unit": "盒"}
    
    instructions: Optional[str] = Field(None, description="医嘱")
    prescribed_date: Optional[date] = Field(None, description="处方日期")
    start_date: Optional[date] = Field(None, description="开始服药日期")


class MedicationCardUpdate(BaseModel):
    """更新用药卡片"""
    sig: Optional[Dict[str, Any]] = None
    dispense: Optional[Dict[str, Any]] = None
    instructions: Optional[str] = None
    status: Optional[str] = None
    end_date: Optional[date] = None


class MedicationCardResponse(BaseModel):
    """用药卡片响应"""
    card_id: str
    patient_id: str
    doctor_id: Optional[str]
    drug_name: str
    generic_name: Optional[str]
    sig: Dict[str, Any]
    dispense: Dict[str, Any]
    instructions: Optional[str]
    prescribed_date: str
    start_date: Optional[str]
    end_date: Optional[str]
    status: str
    source: str
    created_at: str
    updated_at: str
    
    class Config:
        from_attributes = True
    
    @field_validator('prescribed_date', 'start_date', 'end_date', mode='before')
    @classmethod
    def validate_date(cls, v):
        if v is None:
            return None
        if isinstance(v, date):
            return v.isoformat()
        return str(v)
    
    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def validate_datetime(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)


# ============================================
# MedicationSchedule Schemas
# ============================================

class MedicationScheduleResponse(BaseModel):
    """用药计划响应"""
    schedule_id: str
    patient_id: str
    card_id: str
    scheduled_date: str
    scheduled_time: str
    dose: Optional[float]
    dose_unit: Optional[str]
    route: Optional[str]
    taken_at: Optional[str]
    status: str
    notes: Optional[str]
    created_at: str
    
    class Config:
        from_attributes = True
    
    @field_validator('scheduled_date', mode='before')
    @classmethod
    def validate_scheduled_date(cls, v):
        if isinstance(v, date):
            return v.isoformat()
        return str(v)
    
    @field_validator('scheduled_time', mode='before')
    @classmethod
    def validate_scheduled_time(cls, v):
        if isinstance(v, time):
            return v.isoformat()
        return str(v)
    
    @field_validator('taken_at', mode='before')
    @classmethod
    def validate_taken_at(cls, v):
        if v is None:
            return None
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
    
    @field_validator('created_at', mode='before')
    @classmethod
    def validate_created_at(cls, v):
        if isinstance(v, datetime):
            return v.isoformat()
        return str(v)
