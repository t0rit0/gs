"""患者上下文构建器（简化版）

从患者记录中读取文本信息，用于在 EntityGraph 初始化时提供患者上下文。
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from backend.database.models import Patient


@dataclass
class PatientContext:
    """患者上下文（简化版）"""
    patient_id: str
    basic_info: Dict[str, Any]
    # 原始文本记录（用于 LLM 初始化时的上下文）
    patient_text_records: Dict[str, str] = field(default_factory=dict)


class PatientContextBuilder:
    """患者上下文构建器（简化版）

    只读取患者基本信息和文本记录，不解析结构化数据。
    """

    def __init__(
        self,
        max_text_records: int = 50
    ):
        """
        Args:
            max_text_records: 最大文本记录数量限制
        """
        self.max_text_records = max_text_records

    def build(self, db: Session, patient_id: str) -> PatientContext:
        """
        从患者记录构建上下文

        Args:
            db: 数据库 session
            patient_id: 患者 ID

        Returns:
            PatientContext 包含患者基本信息和文本记录
        """
        # 加载患者数据
        patient = db.query(Patient).filter(
            Patient.patient_id == patient_id
        ).first()

        if not patient:
            raise ValueError(f"Patient {patient_id} not found")

        # 构建基本信息
        basic_info = {
            "name": patient.name,
            "age": patient.age,
            "gender": patient.gender,
            "phone": patient.phone,
            "address": patient.address
        }

        # 收集文本记录
        patient_text_records = {}

        # 添加各种文本记录（最多 max_text_records 条）
        self._add_text_record(patient_text_records, "medical_history", patient.medical_history)
        self._add_text_record(patient_text_records, "allergies", patient.allergies)
        self._add_text_record(patient_text_records, "medications", patient.medications)
        self._add_text_record(patient_text_records, "family_history", patient.family_history)
        self._add_text_record(patient_text_records, "health_metrics", patient.health_metrics)

        return PatientContext(
            patient_id=patient_id,
            basic_info=basic_info,
            patient_text_records=patient_text_records
        )

    def _add_text_record(
        self,
        records: Dict[str, str],
        field_name: str,
        value: Any
    ) -> None:
        """
        添加文本记录到字典

        Args:
            records: 记录字典
            field_name: 字段名称
            value: 字段值（可以是列表或单个值）
        """
        if not value:
            return

        # 将值转换为字符串
        if isinstance(value, list):
            # 如果是列表（如 medical_history），合并为文本
            text_value = "\n".join([
                f"- {item}" if isinstance(item, dict) else str(item)
                for item in value
            ])
        elif isinstance(value, dict):
            # 如果是字典，格式化为文本
            parts = [f"{k}: {v}" for k, v in value.items()]
            text_value = "; ".join(parts)
        else:
            # 直接转换为字符串
            text_value = str(value)

        # 只添加非空记录
        if text_value.strip():
            records[field_name] = text_value
