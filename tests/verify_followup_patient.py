#!/usr/bin/env python
"""
验证高血压随访测试患者数据
"""

import sys
from pathlib import Path

project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.models import HealthMetricRecord


def verify_patient(patient_id: str, session: Session):
    """验证患者数据"""
    print("=" * 70)
    print("验证高血压随访测试患者数据")
    print("=" * 70)
    
    # 获取患者
    patient = patient_crud.get(session, patient_id)
    
    if not patient:
        print(f"❌ 患者 {patient_id} 不存在")
        return
    
    print(f"\n✓ 患者信息:")
    print(f"  ID: {patient.patient_id}")
    print(f"  姓名：{patient.name}")
    print(f"  年龄：{patient.age}")
    print(f"  性别：{patient.gender}")
    
    # 既往病史
    print(f"\n✓ 既往病史 ({len(patient.medical_history or [])}):")
    for condition in patient.medical_history or []:
        print(f"  • {condition.get('condition')} - {condition.get('status')}")
    
    # 用药
    print(f"\n✓ 用药史 ({len(patient.medications or [])}):")
    for med in patient.medications or []:
        print(f"  • {med.get('medication_name')} {med.get('dosage')} - {med.get('frequency')}")
    
    # 症状
    print(f"\n✓ 症状 ({len(patient.symptoms or [])}):")
    for symptom in patient.symptoms or []:
        print(f"  • {symptom.get('symptom')} - {symptom.get('status')}")
    
    # 健康指标
    print(f"\n✓ 健康指标统计:")
    
    all_metrics = session.query(HealthMetricRecord).filter(
        HealthMetricRecord.patient_id == patient_id
    ).all()
    
    # 按指标名称分组
    from collections import defaultdict
    metrics_by_name = defaultdict(list)
    for m in all_metrics:
        metrics_by_name[m.metric_name].append(m)
    
    for metric_name, records in sorted(metrics_by_name.items()):
        latest = max(records, key=lambda x: x.measured_at)
        earliest = min(records, key=lambda x: x.measured_at)
        days_span = (latest.measured_at - earliest.measured_at).days
        print(f"  • {metric_name}: {latest.value_string} ({len(records)}条记录，跨度{days_span}天)")
    
    # 血压趋势
    print(f"\n✓ 14 天血压趋势:")
    bp_records = sorted(
        [m for m in all_metrics if m.metric_name == "Blood Pressure"],
        key=lambda x: x.measured_at
    )
    
    # 按天分组显示
    from datetime import date
    by_date = defaultdict(list)
    for r in bp_records:
        by_date[r.measured_at.date()].append(r)
    
    for d in sorted(by_date.keys()):
        records = by_date[d]
        if len(records) >= 2:
            morning = records[0].value_string
            evening = records[1].value_string
            day_num = (d - bp_records[0].measured_at.date()).days + 1
            print(f"  第{day_num:2d}天 ({d.strftime('%m-%d')})：早 {morning} | 晚 {evening}")
    
    # 对话历史
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
        # 使用最新创建的患者 ID
        patient_id = "97304e23-0a8d-48d9-bff4-d556960fefe4"
        verify_patient(patient_id, session)
    finally:
        session.close()
