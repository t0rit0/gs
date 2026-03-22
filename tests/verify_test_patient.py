#!/usr/bin/env python
"""
验证测试患者数据
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.services.metric_crud import MetricCRUD


def verify_patient(patient_id: str, session: Session):
    """Verify patient data"""
    print("=" * 70)
    print("验证测试患者数据")
    print("=" * 70)
    
    # Get patient
    patient = patient_crud.get(session, patient_id)
    
    if not patient:
        print(f"❌ 患者 {patient_id} 不存在")
        return
    
    print(f"\n✓ 患者信息:")
    print(f"  ID: {patient.patient_id}")
    print(f"  姓名：{patient.name}")
    print(f"  年龄：{patient.age}")
    print(f"  性别：{patient.gender}")
    
    # Medical history
    print(f"\n✓ 既往病史 ({len(patient.medical_history or [])}):")
    for condition in patient.medical_history or []:
        print(f"  • {condition.get('condition')} - {condition.get('status')}")
    
    # Medications
    print(f"\n✓ 用药史 ({len(patient.medications or [])}):")
    for med in patient.medications or []:
        print(f"  • {med.get('medication_name')} {med.get('dosage')} - {med.get('frequency')}")
    
    # Symptoms
    print(f"\n✓ 症状 ({len(patient.symptoms or [])}):")
    for symptom in patient.symptoms or []:
        print(f"  • {symptom.get('symptom')} - {symptom.get('status')}")
    
    # Health Metrics
    print(f"\n✓ 健康指标统计:")
    
    # Get all metrics using get_records
    from backend.database.models import HealthMetricRecord
    all_metrics = session.query(HealthMetricRecord).filter(
        HealthMetricRecord.patient_id == patient_id
    ).all()
    
    # Group by metric name
    from collections import defaultdict
    metrics_by_name = defaultdict(list)
    for m in all_metrics:
        metrics_by_name[m.metric_name].append(m)
    
    for metric_name, records in sorted(metrics_by_name.items()):
        latest = max(records, key=lambda x: x.measured_at)
        print(f"  • {metric_name}: {latest.value_string} ({len(records)} 条记录)")
    
    # Blood Pressure trend
    print(f"\n✓ 血压趋势:")
    bp_records = sorted(
        [m for m in all_metrics if m.metric_name == "Blood Pressure"],
        key=lambda x: x.measured_at
    )
    for record in bp_records[-5:]:  # Last 5 readings
        print(f"  {record.measured_at.strftime('%Y-%m-%d')}: {record.value_string}")
    
    # Conversations
    from backend.database.models import Conversation
    conv_count = session.query(Conversation).filter(
        Conversation.patient_id == patient_id
    ).count()
    print(f"\n✓ 对话历史：{conv_count} 条")
    
    print("\n" + "=" * 70)
    print("✅ 数据验证完成")
    print("=" * 70)


if __name__ == "__main__":
    session = SessionLocal()
    try:
        # Use the latest patient ID
        patient_id = "7497dbc9-a022-4f3b-916d-493154cceec7"
        verify_patient(patient_id, session)
    finally:
        session.close()
