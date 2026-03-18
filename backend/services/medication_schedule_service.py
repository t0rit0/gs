"""
Medication Schedule Service

TDD Implementation - MedicationScheduleService
"""

from typing import List, Optional, Dict
from datetime import datetime, date, time, timedelta
from sqlalchemy.orm import Session
from backend.database.models import MedicationSchedule, MedicationCard


class MedicationScheduleService:
    """
    用药计划服务
    
    负责:
    1. 生成每日计划
    2. 确认服药
    3. 查询历史
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def generate_todays_schedules(self, patient_id: str) -> int:
        """
        为患者生成今天的用药计划
        """
        return self.generate_schedules(patient_id, date.today())
    
    def generate_schedules(
        self,
        patient_id: str,
        target_date: date
    ) -> int:
        """
        为患者生成指定日期的用药计划
        """
        # Check if already generated
        existing = self.db.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == patient_id,
            MedicationSchedule.scheduled_date == target_date
        ).count()
        
        if existing > 0:
            return 0  # Already generated
        
        # Get all active cards
        cards = self.db.query(MedicationCard).filter(
            MedicationCard.patient_id == patient_id,
            MedicationCard.status == "active",
            MedicationCard.start_date <= target_date,
            (MedicationCard.end_date == None) | (MedicationCard.end_date >= target_date)
        ).all()
        
        count = 0
        
        for card in cards:
            count += self._generate_schedules_for_card(
                patient_id=patient_id,
                card_id=card.card_id,
                target_date=target_date
            )
        
        return count
    
    def _generate_schedules_for_card(
        self,
        patient_id: str,
        card_id: str,
        target_date: date
    ) -> int:
        """
        为单个卡片生成指定日期的计划
        """
        card = self.db.query(MedicationCard).filter(
            MedicationCard.card_id == card_id,
            MedicationCard.patient_id == patient_id
        ).first()
        
        if not card:
            return 0
        
        # Parse frequency to time slots
        time_slots = self._parse_frequency_to_times(card.sig.get("frequency", "一天一次"))
        
        count = 0
        
        for time_str in time_slots:
            schedule = MedicationSchedule(
                patient_id=patient_id,
                card_id=card_id,
                scheduled_date=target_date,
                scheduled_time=datetime.strptime(time_str, "%H:%M").time(),
                dose=card.sig.get("dose"),
                dose_unit=card.sig.get("dose_unit"),
                route=card.sig.get("route"),
                status="pending"
            )
            
            self.db.add(schedule)
            count += 1
        
        self.db.commit()
        
        return count
    
    def _parse_frequency_to_times(self, frequency: str) -> List[str]:
        """
        解析频率为具体时间槽
        """
        time_map = {
            "一天一次": ["08:00"],
            "一天两次": ["08:00", "20:00"],
            "一天三次": ["08:00", "14:00", "20:00"],
            "每 8 小时": ["06:00", "14:00", "22:00"],
            "每 12 小时": ["08:00", "20:00"]
        }
        
        return time_map.get(frequency, ["08:00"])
    
    def confirm_medication(
        self,
        schedule_id: str,
        taken_at: datetime = None,
        notes: str = None
    ) -> Optional[MedicationSchedule]:
        """
        确认服药
        """
        schedule = self.db.query(MedicationSchedule).filter(
            MedicationSchedule.schedule_id == schedule_id
        ).first()
        
        if not schedule:
            return None
        
        schedule.taken_at = taken_at or datetime.now()
        schedule.status = "completed"
        
        if notes:
            schedule.notes = notes
        
        self.db.commit()
        self.db.refresh(schedule)
        
        return schedule
    
    def get_today_schedules(self, patient_id: str) -> List[MedicationSchedule]:
        """获取今天的用药计划"""
        return self.db.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == patient_id,
            MedicationSchedule.scheduled_date == date.today()
        ).order_by(MedicationSchedule.scheduled_time).all()
    
    def get_schedules_by_date(
        self,
        patient_id: str,
        target_date: date
    ) -> List[MedicationSchedule]:
        """获取指定日期的用药计划"""
        return self.db.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == patient_id,
            MedicationSchedule.scheduled_date == target_date
        ).order_by(MedicationSchedule.scheduled_time).all()
    
    def get_medication_history(
        self,
        patient_id: str,
        start_date: date,
        end_date: date,
        card_id: str = None
    ) -> List[MedicationSchedule]:
        """获取用药历史记录"""
        query = self.db.query(MedicationSchedule).filter(
            MedicationSchedule.patient_id == patient_id,
            MedicationSchedule.scheduled_date >= start_date,
            MedicationSchedule.scheduled_date <= end_date
        )
        
        if card_id:
            query = query.filter(MedicationSchedule.card_id == card_id)
        
        query = query.order_by(MedicationSchedule.scheduled_date.desc())
        
        return query.all()
    
    def get_medication_summary(
        self,
        patient_id: str,
        days: int = 30
    ) -> Dict:
        """获取用药统计"""
        end_date = date.today()
        start_date = end_date - timedelta(days=days)
        
        schedules = self.get_medication_history(patient_id, start_date, end_date)
        
        total = len(schedules)
        completed = len([s for s in schedules if s.status == "completed"])
        missed = len([s for s in schedules if s.status == "missed"])
        pending = len([s for s in schedules if s.status == "pending"])
        
        completion_rate = (completed / total * 100) if total > 0 else 0
        
        return {
            "total_schedules": total,
            "completed": completed,
            "missed": missed,
            "pending": pending,
            "completion_rate": round(completion_rate, 1)
        }
