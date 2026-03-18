"""
Medication Management API Endpoints

TDD Implementation - Medication API
"""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from typing import List, Dict, Any
from datetime import date, datetime
import io
import pandas as pd

from backend.database.base import get_db
from backend.services.medication_card_service import MedicationCardService
from backend.services.medication_schedule_service import MedicationScheduleService
from backend.api.medication_schemas import (
    MedicationCardCreate,
    MedicationCardUpdate,
    MedicationCardResponse,
    MedicationScheduleResponse
)

# Create routers
medication_router = APIRouter(prefix="/api/patients/{patient_id}/medications", tags=["Medications"])
schedule_router = APIRouter(prefix="/api/patients/{patient_id}/schedules", tags=["Medication Schedules"])


# ============================================
# Medication Card Endpoints
# ============================================

@medication_router.post("", response_model=MedicationCardResponse, status_code=201)
def create_medication_card(
    patient_id: str,
    card: MedicationCardCreate,
    db: Session = Depends(get_db)
):
    """
    创建用药卡片/处方
    
    - **drug_name**: 药品名称 "阿莫西林胶囊"
    - **sig**: 用药说明 {dose, dose_unit, route, frequency, duration_days}
    - **dispense**: 配药信息 {total_quantity, quantity_unit}
    - **instructions**: 医嘱 "饭后服用"
    """
    service = MedicationCardService(db)
    
    record = service.create_card(
        patient_id=patient_id,
        drug_name=card.drug_name,
        sig=card.sig,
        generic_name=card.generic_name,
        dispense=card.dispense,
        instructions=card.instructions,
        prescribed_date=card.prescribed_date,
        start_date=card.start_date
    )
    
    return record


@medication_router.get("", response_model=List[MedicationCardResponse])
def get_patient_medication_cards(
    patient_id: str,
    status: str = Query("all", description="过滤状态"),
    db: Session = Depends(get_db)
):
    """
    获取患者用药卡片
    
    - **status**: "active" | "completed" | "discontinued" | "all"
    """
    service = MedicationCardService(db)
    return service.get_patient_cards(patient_id, status)


@medication_router.get("/{card_id}", response_model=MedicationCardResponse)
def get_medication_card(
    patient_id: str,
    card_id: str,
    db: Session = Depends(get_db)
):
    """获取单个用药卡片"""
    service = MedicationCardService(db)
    card = service.get_card(card_id)
    
    if not card:
        raise HTTPException(status_code=404, detail="Medication card not found")
    
    return card


@medication_router.put("/{card_id}", response_model=MedicationCardResponse)
def update_medication_card(
    patient_id: str,
    card_id: str,
    updates: MedicationCardUpdate,
    db: Session = Depends(get_db)
):
    """
    更新用药卡片
    
    - 剂量调整
    - 停药
    - 修改医嘱
    """
    service = MedicationCardService(db)
    card = service.update_card(card_id, updates.dict(exclude_unset=True))
    
    if not card:
        raise HTTPException(status_code=404, detail="Medication card not found")
    
    return card


@medication_router.post("/{card_id}/complete", response_model=MedicationCardResponse)
def complete_medication_card(
    patient_id: str,
    card_id: str,
    db: Session = Depends(get_db)
):
    """标记为已完成疗程"""
    service = MedicationCardService(db)
    card = service.complete_card(card_id)
    
    if not card:
        raise HTTPException(status_code=404, detail="Medication card not found")
    
    return card


@medication_router.post("/{card_id}/discontinue", response_model=MedicationCardResponse)
def discontinue_medication_card(
    patient_id: str,
    card_id: str,
    reason: str = Query(None, description="停药原因"),
    db: Session = Depends(get_db)
):
    """停药"""
    service = MedicationCardService(db)
    card = service.discontinue_card(card_id, reason)
    
    if not card:
        raise HTTPException(status_code=404, detail="Medication card not found")
    
    return card


# ============================================
# Medication Schedule Endpoints
# ============================================

@schedule_router.get("/today", response_model=List[MedicationScheduleResponse])
def get_today_schedules(
    patient_id: str,
    db: Session = Depends(get_db)
):
    """获取今天的用药计划"""
    service = MedicationScheduleService(db)
    return service.get_today_schedules(patient_id)


@schedule_router.post("/{schedule_id}/confirm", response_model=MedicationScheduleResponse)
def confirm_medication(
    patient_id: str,
    schedule_id: str,
    taken_at: str = None,
    notes: str = None,
    db: Session = Depends(get_db)
):
    """
    确认服药
    
    - **taken_at**: 实际服药时间 (ISO format)
    - **notes**: 备注
    """
    service = MedicationScheduleService(db)
    
    taken_at_dt = None
    if taken_at:
        taken_at_dt = datetime.fromisoformat(taken_at)
    
    schedule = service.confirm_medication(schedule_id, taken_at_dt, notes)
    
    if not schedule:
        raise HTTPException(status_code=404, detail="Schedule not found")
    
    return schedule


@schedule_router.get("/history/summary")
def get_medication_summary(
    patient_id: str,
    days: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """获取用药统计"""
    service = MedicationScheduleService(db)
    return service.get_medication_summary(patient_id, days)


# Export for server.py
__all__ = ["medication_router", "schedule_router"]
