"""
Medication Card Service

TDD Implementation - MedicationCardService
"""

from typing import List, Optional, Dict, Any
from datetime import datetime, date, timedelta
from sqlalchemy.orm import Session
from backend.database.models import MedicationCard


class MedicationCardService:
    """
    用药卡片管理服务
    """
    
    def __init__(self, db: Session):
        self.db = db
    
    def create_card(
        self,
        patient_id: str,
        drug_name: str,
        sig: Dict,
        doctor_id: str = None,
        generic_name: str = None,
        dispense: Dict = None,
        instructions: str = None,
        prescribed_date: date = None,
        start_date: date = None,
        source: str = "manual",
        conversation_id: str = None,
        report_id: str = None
    ) -> MedicationCard:
        """
        创建用药卡片
        """
        # Default prescribed_date to today
        if prescribed_date is None:
            prescribed_date = date.today()
        
        # Default start_date to prescribed_date
        if start_date is None:
            start_date = prescribed_date
        
        # Calculate end_date from duration_days
        end_date = None
        if sig.get("duration_days"):
            end_date = prescribed_date + timedelta(days=sig["duration_days"])
        
        # Determine initial status
        status = "active" if start_date <= date.today() else "pending"
        
        card = MedicationCard(
            patient_id=patient_id,
            doctor_id=doctor_id,
            drug_name=drug_name,
            generic_name=generic_name,
            sig=sig,
            dispense=dispense or {},
            instructions=instructions,
            prescribed_date=prescribed_date,
            start_date=start_date,
            end_date=end_date,
            source=source,
            conversation_id=conversation_id,
            report_id=report_id,
            status=status
        )
        
        self.db.add(card)
        self.db.commit()
        self.db.refresh(card)
        
        # Auto-generate today's schedules
        from backend.services.medication_schedule_service import MedicationScheduleService
        MedicationScheduleService(self.db).generate_todays_schedules(patient_id)
        
        return card
    
    def get_patient_cards(
        self,
        patient_id: str,
        status: str = "all"
    ) -> List[MedicationCard]:
        """
        获取患者用药卡片
        """
        query = self.db.query(MedicationCard).filter(
            MedicationCard.patient_id == patient_id
        )
        
        if status != "all":
            query = query.filter(MedicationCard.status == status)
        
        query = query.order_by(MedicationCard.prescribed_date.desc())
        
        return query.all()
    
    def get_card(self, card_id: str) -> Optional[MedicationCard]:
        """获取单个卡片"""
        return self.db.query(MedicationCard).filter(
            MedicationCard.card_id == card_id
        ).first()
    
    def update_card(
        self,
        card_id: str,
        updates: Dict[str, Any]
    ) -> Optional[MedicationCard]:
        """
        更新用药卡片
        """
        card = self.get_card(card_id)
        
        if not card:
            return None
        
        allowed_fields = [
            "sig", "dispense", "instructions",
            "status", "end_date", "start_date"
        ]
        
        for field in allowed_fields:
            if field in updates:
                setattr(card, field, updates[field])
        
        # Recalculate end_date if sig changed
        if "sig" in updates and updates["sig"].get("duration_days"):
            card.end_date = card.calculate_end_date()
        
        card.updated_at = datetime.now()
        
        self.db.commit()
        self.db.refresh(card)
        
        return card
    
    def complete_card(
        self,
        card_id: str
    ) -> Optional[MedicationCard]:
        """
        标记为已完成疗程
        """
        return self.update_card(card_id, {
            "status": "completed",
            "end_date": date.today()
        })
    
    def discontinue_card(
        self,
        card_id: str,
        reason: str = None
    ) -> Optional[MedicationCard]:
        """
        停药
        """
        updates = {
            "status": "discontinued",
            "end_date": date.today()
        }
        
        if reason:
            # Append to instructions
            card = self.get_card(card_id)
            if card:
                updates["instructions"] = (card.instructions or "") + f"\n[停药原因：{reason}]"
        
        return self.update_card(card_id, updates)
    
    def import_cards_from_csv(
        self,
        patient_id: str,
        doctor_id: str,
        csv_data: List[Dict]
    ) -> Dict[str, int]:
        """
        从 CSV 导入用药卡片
        """
        imported = 0
        skipped = 0
        errors = []
        
        for idx, row in enumerate(csv_data):
            try:
                # Validate required fields
                required = ["drug_name", "dose", "frequency"]
                missing = [f for f in required if f not in row]
                if missing:
                    errors.append(f"Row {idx+1}: 缺少字段 {missing}")
                    skipped += 1
                    continue
                
                # Build sig
                sig = {
                    "dose": float(row["dose"]),
                    "dose_unit": row.get("dose_unit", "g"),
                    "route": row.get("route", "口服"),
                    "frequency": row["frequency"],
                    "duration_days": int(row.get("duration_days", 0))
                }
                
                # Build dispense
                dispense = {}
                if row.get("total_quantity"):
                    dispense["total_quantity"] = int(row["total_quantity"])
                    dispense["quantity_unit"] = row.get("quantity_unit", "盒")
                
                # Create card
                self.create_card(
                    patient_id=patient_id,
                    doctor_id=doctor_id,
                    drug_name=row["drug_name"],
                    sig=sig,
                    dispense=dispense if dispense else None,
                    instructions=row.get("instructions"),
                    source="csv_import"
                )
                
                imported += 1
                
            except Exception as e:
                errors.append(f"Row {idx+1}: {str(e)}")
                skipped += 1
        
        return {
            "imported": imported,
            "skipped": skipped,
            "errors": errors
        }
    
    def export_cards_to_csv(
        self,
        patient_id: str,
        status: str = "all"
    ) -> List[Dict]:
        """
        导出用药卡片为 CSV 格式
        """
        import json
        
        cards = self.get_patient_cards(patient_id, status)
        
        return [
            {
                "drug_name": card.drug_name,
                "generic_name": card.generic_name or "",
                "dose": card.sig.get("dose", ""),
                "dose_unit": card.sig.get("dose_unit", ""),
                "route": card.sig.get("route", ""),
                "frequency": card.sig.get("frequency", ""),
                "duration_days": card.sig.get("duration_days", ""),
                "total_quantity": card.dispense.get("total_quantity", ""),
                "quantity_unit": card.dispense.get("quantity_unit", ""),
                "instructions": card.instructions or "",
                "prescribed_date": card.prescribed_date.isoformat(),
                "status": card.status
            }
            for card in cards
        ]
