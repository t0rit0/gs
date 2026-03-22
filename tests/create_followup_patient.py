#!/usr/bin/env python
"""
创建高血压随访测试患者（2 周详细数据）

基于真实高血压随访病例的典型数据：
- 52 岁女性
- 2 期高血压，确诊 6 个月
- 14 天详细血压记录（每日早晚测量）
- 完整症状追踪
- 多种合并症
- 调整用药过程

数据来源：基于 AHA/ACC 高血压管理指南典型病例
"""

import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent.parent
sys.path.insert(0, str(project_root))

from sqlalchemy.orm import Session
from backend.database.base import SessionLocal
from backend.database.crud import patient_crud
from backend.database.schemas import PatientCreate
from backend.services.metric_crud import MetricCRUD


def create_hypertension_followup_patient(session: Session) -> str:
    """
    创建高血压随访测试患者（2 周数据）
    
    Returns:
        Patient ID
    """
    print("=" * 70)
    print("创建高血压随访测试患者（2 周详细数据）")
    print("=" * 70)
    
    # 清理现有测试患者
    from backend.database.models import Patient, HealthMetricRecord
    existing = session.query(Patient).filter(
        Patient.name.like("高血压随访测试%")
    ).all()
    for p in existing:
        session.delete(p)
    session.commit()
    print("✓ 已清理旧测试数据")
    
    # ============================================
    # 1. 创建患者基本信息
    # ============================================
    print("\n[1/5] 创建患者基本信息...")
    
    patient = patient_crud.create(session, PatientCreate(
        name="高血压随访测试患者 - 李梅",
        age=52,
        gender="female",
        phone="13900139052",
        address="上海市浦东新区世纪大道 1000 号",
        occupation="中学教师",
        
        # 既往病史
        medical_history=[
            {
                "condition": "高血压病 2 级",
                "diagnosis_date": "2025-07-15T00:00:00",
                "status": "chronic",
                "notes": "确诊时血压 155/98 mmHg，开始生活方式干预"
            },
            {
                "condition": "2 型糖尿病",
                "diagnosis_date": "2023-03-10T00:00:00",
                "status": "chronic",
                "notes": "确诊时 HbA1c 7.8%，目前控制良好"
            },
            {
                "condition": "高脂血症",
                "diagnosis_date": "2024-01-20T00:00:00",
                "status": "active",
                "notes": "LDL 165 mg/dL，开始他汀治疗"
            },
            {
                "condition": "甲状腺功能减退",
                "diagnosis_date": "2020-06-15T00:00:00",
                "status": "chronic",
                "notes": "服用左甲状腺素钠片"
            },
            {
                "condition": "骨质疏松症",
                "diagnosis_date": "2024-08-01T00:00:00",
                "status": "chronic",
                "notes": "骨密度 T 值 -2.8"
            }
        ],
        
        # 家族史
        family_history=[
            {
                "relation": "父亲",
                "condition": "高血压、冠心病",
                "age_at_diagnosis": 50,
                "notes": "65 岁发生心肌梗死"
            },
            {
                "relation": "母亲",
                "condition": "2 型糖尿病、高血压",
                "age_at_diagnosis": 55,
                "notes": ""
            },
            {
                "relation": "妹妹",
                "condition": "甲状腺功能减退",
                "age_at_diagnosis": 48,
                "notes": ""
            }
        ],
        
        # 过敏史
        allergies=[
            {
                "allergen": "磺胺类药物",
                "severity": "severe",
                "reaction": "严重皮疹、呼吸困难",
                "diagnosed_date": "2015-08-20T00:00:00"
            },
            {
                "allergen": "海鲜",
                "severity": "moderate",
                "reaction": "荨麻疹",
                "diagnosed_date": "2010-05-10T00:00:00"
            }
        ],
        
        # 用药史
        medications=[
            {
                "medication_name": "硝苯地平控释片",
                "dosage": "30mg",
                "frequency": "每日一次",
                "start_date": "2025-07-15T00:00:00",
                "prescribing_doctor": "王医生",
                "notes": "钙通道阻滞剂"
            },
            {
                "medication_name": "缬沙坦",
                "dosage": "80mg",
                "frequency": "每日一次",
                "start_date": "2025-08-01T00:00:00",
                "prescribing_doctor": "王医生",
                "notes": "ARB 类降压药"
            },
            {
                "medication_name": "二甲双胍",
                "dosage": "500mg",
                "frequency": "每日三次",
                "start_date": "2023-03-10T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "降糖药"
            },
            {
                "medication_name": "阿托伐他汀",
                "dosage": "20mg",
                "frequency": "每晚一次",
                "start_date": "2024-01-20T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "降胆固醇"
            },
            {
                "medication_name": "左甲状腺素钠片",
                "dosage": "50μg",
                "frequency": "每日一次",
                "start_date": "2020-06-15T00:00:00",
                "prescribing_doctor": "张医生",
                "notes": "甲状腺素替代"
            },
            {
                "medication_name": "阿仑膦酸钠",
                "dosage": "70mg",
                "frequency": "每周一次",
                "start_date": "2024-08-01T00:00:00",
                "prescribing_doctor": "张医生",
                "notes": "抗骨质疏松"
            }
        ],
        
        # 生活方式
        lifestyle={
            "smoking_status": "never",
            "alcohol_consumption": "偶尔，每月 1-2 次红酒",
            "exercise_frequency": "每周 3-4 次，每次 30 分钟快走",
            "diet_notes": "低盐饮食（估计 2000mg/天），多吃蔬菜水果",
            "sleep_quality": "一般，每晚 6-7 小时",
            "stress_level": "中等，工作压力较大"
        }
    ))
    
    print(f"✓ 患者创建成功：{patient.patient_id}")
    print(f"  姓名：{patient.name}")
    print(f"  年龄：{patient.age}岁")
    print(f"  性别：{patient.gender}")
    
    # ============================================
    # 2. 创建 14 天血压记录（每日早晚测量）
    # ============================================
    print("\n[2/5] 创建 14 天血压记录...")
    
    # 从 14 天前开始
    base_date = datetime.now() - timedelta(days=14)
    
    # 14 天血压数据（模拟真实随访数据）
    bp_data = [
        # (第几天，早晨血压，晚上血压，心率，备注)
        (0, "148/94", "152/96", "78", "开始记录，感觉头晕"),
        (1, "145/92", "149/95", "76", "服药后有所改善"),
        (2, "142/90", "146/93", "74", "症状减轻"),
        (3, "140/88", "144/91", "72", "感觉良好"),
        (4, "138/86", "142/89", "70", "继续服药"),
        (5, "136/84", "140/88", "72", "血压稳定"),
        (6, "135/83", "139/87", "71", "周末休息好"),
        (7, "137/85", "141/89", "73", "复诊日"),
        (8, "139/87", "143/91", "75", "调整用药后"),
        (9, "136/84", "140/88", "72", "感觉良好"),
        (10, "134/82", "138/86", "70", "血压控制理想"),
        (11, "133/81", "137/85", "69", "继续坚持"),
        (12, "132/80", "136/84", "71", "状态稳定"),
        (13, "131/79", "135/83", "70", "记录结束"),
    ]
    
    for day, morning_bp, evening_bp, hr, notes in bp_data:
        date = base_date + timedelta(days=day)
        
        # 早晨测量（6:00-8:00）
        morning_time = date.replace(hour=7, minute=0, second=0)
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value=morning_bp,
            measured_at=morning_time,
            context=f"早晨测量 - {notes}"
        )
        
        # 晚上测量（19:00-21:00）
        evening_time = date.replace(hour=20, minute=0, second=0)
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value=evening_bp,
            measured_at=evening_time,
            context=f"晚上测量 - {notes}"
        )
        
        # 心率
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Heart Rate",
            value=hr,
            unit="bpm",
            measured_at=morning_time,
            context=f"静息心率 - 早晨"
        )
    
    print(f"  ✓ 创建了 {len(bp_data) * 3} 条记录（14 天 x 每日 3 次测量）")
    
    # ============================================
    # 3. 创建其他健康指标
    # ============================================
    print("\n[3/5] 创建其他健康指标...")
    
    now = datetime.now()
    
    # 基线检查（14 天前）
    baseline_metrics = [
        {"name": "Glucose", "value": "135", "unit": "mg/dL", "notes": "空腹血糖，偏高"},
        {"name": "HbA1c", "value": "7.2", "unit": "%", "notes": "糖尿病控制一般"},
        {"name": "Total Cholesterol", "value": "225", "unit": "mg/dL", "notes": "偏高"},
        {"name": "LDL Cholesterol", "value": "145", "unit": "mg/dL", "notes": "偏高"},
        {"name": "HDL Cholesterol", "value": "48", "unit": "mg/dL", "notes": "正常"},
        {"name": "Triglycerides", "value": "185", "unit": "mg/dL", "notes": "偏高"},
        {"name": "Creatinine", "value": "0.9", "unit": "mg/dL", "notes": "正常"},
        {"name": "eGFR", "value": "85", "unit": "mL/min/1.73m²", "notes": "正常"},
        {"name": "TSH", "value": "2.5", "unit": "mIU/L", "notes": "甲状腺功能正常"},
        {"name": "Weight", "value": "68", "unit": "kg", "notes": "基线体重"},
        {"name": "BMI", "value": "26.5", "unit": "kg/m²", "notes": "超重"},
    ]
    
    for metric in baseline_metrics:
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name=metric["name"],
            value=metric["value"],
            unit=metric["unit"],
            measured_at=base_date,
            context=metric["notes"]
        )
    
    # 复查指标（第 7 天）
    followup_metrics = [
        {"name": "Glucose", "value": "118", "unit": "mg/dL", "notes": "空腹血糖，有所改善"},
        {"name": "Weight", "value": "67.2", "unit": "kg", "notes": "减轻 0.8kg"},
    ]
    
    for metric in followup_metrics:
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name=metric["name"],
            value=metric["value"],
            unit=metric["unit"],
            measured_at=base_date + timedelta(days=7),
            context=metric["notes"]
        )
    
    # 最新指标（今天）
    latest_metrics = [
        {"name": "Glucose", "value": "112", "unit": "mg/dL", "notes": "空腹血糖，控制良好"},
        {"name": "Weight", "value": "66.5", "unit": "kg", "notes": "减轻 1.5kg"},
        {"name": "Systolic BP", "value": "131", "unit": "mmHg", "notes": "最新收缩压"},
        {"name": "Diastolic BP", "value": "79", "unit": "mmHg", "notes": "最新舒张压"},
    ]
    
    for metric in latest_metrics:
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name=metric["name"],
            value=metric["value"],
            unit=metric["unit"],
            measured_at=now,
            context=metric["notes"]
        )
    
    print(f"  ✓ 创建了 {len(baseline_metrics) + len(followup_metrics) + len(latest_metrics)} 项其他指标")
    
    # ============================================
    # 4. 创建症状记录（动态变化）
    # ============================================
    print("\n[4/5] 创建症状记录...")
    
    # 活动性症状
    active_symptoms = [
        {
            "symptom": "头痛",
            "description": "轻度头痛，主要在早晨，血压高时明显",
            "status": "active",
            "severity": "mild",
            "frequency": "几乎每日",
            "onset_date": (now - timedelta(days=30)).strftime('%Y-%m-%d'),
            "improvement_notes": "血压控制后有所减轻"
        },
        {
            "symptom": "头晕",
            "description": "快速站立或转头时偶发头晕",
            "status": "active",
            "severity": "mild",
            "frequency": "偶发",
            "onset_date": (now - timedelta(days=20)).strftime('%Y-%m-%d'),
            "improvement_notes": "近期发作减少"
        },
        {
            "symptom": "疲劳",
            "description": "下午感到疲劳，精力不足",
            "status": "active",
            "severity": "moderate",
            "frequency": "每日",
            "onset_date": (now - timedelta(days=15)).strftime('%Y-%m-%d'),
            "improvement_notes": "休息后可缓解"
        },
        {
            "symptom": "心悸",
            "description": "紧张或劳累时感到心跳加快",
            "status": "active",
            "severity": "mild",
            "frequency": "偶发",
            "onset_date": (now - timedelta(days=10)).strftime('%Y-%m-%d'),
            "improvement_notes": "血压稳定后减少"
        },
        {
            "symptom": "睡眠质量差",
            "description": "入睡困难，夜间易醒",
            "status": "active",
            "severity": "moderate",
            "frequency": "每周 3-4 次",
            "onset_date": (now - timedelta(days=25)).strftime('%Y-%m-%d'),
            "improvement_notes": "工作压力大时加重"
        },
        {
            "symptom": "口干",
            "description": "经常感到口干，需要频繁饮水",
            "status": "active",
            "severity": "mild",
            "frequency": "每日",
            "onset_date": (now - timedelta(days=60)).strftime('%Y-%m-%d'),
            "improvement_notes": "可能与糖尿病有关"
        }
    ]
    
    for symptom in active_symptoms:
        patient_crud.add_symptom(
            db=session,
            patient_id=patient.patient_id,
            symptom=symptom["symptom"],
            description=symptom["description"],
            status="active"
        )
        print(f"  ✓ 症状：{symptom['symptom']} (活动性)")
    
    # 已缓解症状
    resolved_symptoms = [
        {
            "symptom": "恶心",
            "description": "血压突然升高时感到恶心",
            "status": "resolved",
            "severity": "moderate",
            "onset_date": (now - timedelta(days=20)).strftime('%Y-%m-%d'),
            "resolution_date": (now - timedelta(days=10)).strftime('%Y-%m-%d'),
            "resolution_notes": "血压控制后消失"
        },
        {
            "symptom": "视力模糊",
            "description": "血压高时短暂视力模糊",
            "status": "resolved",
            "severity": "moderate",
            "onset_date": (now - timedelta(days=18)).strftime('%Y-%m-%d'),
            "resolution_date": (now - timedelta(days=7)).strftime('%Y-%m-%d'),
            "resolution_notes": "血压稳定后未再发作"
        }
    ]
    
    for symptom in resolved_symptoms:
        patient_crud.add_symptom(
            db=session,
            patient_id=patient.patient_id,
            symptom=symptom["symptom"],
            description=symptom["description"],
            status="resolved"
        )
        print(f"  ✓ 症状：{symptom['symptom']} (已缓解)")
    
    # ============================================
    # 5. 创建随访记录
    # ============================================
    print("\n[5/5] 创建随访记录...")
    
    # 这里可以添加随访记录到 conversations 表
    # 但根据要求，我们不创建对话历史
    
    print("  ✓ 随访记录已准备（无对话历史）")
    
    # 提交所有更改
    session.commit()
    
    # ============================================
    # 总结
    # ============================================
    print("\n" + "=" * 70)
    print("✅ 高血压随访测试患者创建完成")
    print("=" * 70)
    print(f"\n患者 ID: {patient.patient_id}")
    print(f"姓名：{patient.name}")
    print(f"年龄：{patient.age}岁，性别：{patient.gender}")
    
    print("\n📋 诊断摘要:")
    print("  • 高血压病 2 级（确诊 2025-07-15）")
    print("  • 2 型糖尿病（确诊 2023-03-10）")
    print("  • 高脂血症")
    print("  • 甲状腺功能减退")
    print("  • 骨质疏松症")
    
    print("\n💊 当前用药（6 种）:")
    print("  • 硝苯地平控释片 30mg qd")
    print("  • 缬沙坦 80mg qd")
    print("  • 二甲双胍 500mg tid")
    print("  • 阿托伐他汀 20mg qn")
    print("  • 左甲状腺素钠片 50μg qd")
    print("  • 阿仑膦酸钠 70mg qw")
    
    print("\n📊 14 天血压趋势:")
    print(f"  • 起始（第 1 天）：{bp_data[0][1]} / {bp_data[0][2]} mmHg")
    print(f"  • 最高：152/96 mmHg（第 1 天晚上）")
    print(f"  • 最新（第 14 天）：{bp_data[-1][1]} / {bp_data[-1][2]} mmHg")
    print(f"  • 目标：<130/80 mmHg")
    print(f"  • 改善：-17/-15 mmHg")
    
    print("\n📈 其他指标变化:")
    print("  • 空腹血糖：135 → 112 mg/dL（改善）")
    print("  • 体重：68 → 66.5 kg（减轻 1.5kg）")
    print("  • HbA1c: 7.2%（糖尿病控制一般）")
    print("  • LDL: 145 mg/dL（偏高）")
    
    print("\n🔍 症状（6 项活动性，2 项已缓解）:")
    print("  活动性:")
    for s in active_symptoms[:3]:
        print(f"    • {s['symptom']} - {s['severity']}")
    print("  已缓解:")
    for s in resolved_symptoms:
        print(f"    • {s['symptom']} - 已缓解")
    
    print("\n📅 数据时间跨度:")
    print(f"  • 开始日期：{base_date.strftime('%Y-%m-%d')}")
    print(f"  • 结束日期：{now.strftime('%Y-%m-%d')}")
    print(f"  • 总计：14 天")
    
    print("\n" + "=" * 70)
    print(f"提示：使用此患者 ID 进行测试：{patient.patient_id}")
    print("=" * 70)
    
    return patient.patient_id


def main():
    """主函数"""
    session = SessionLocal()
    
    try:
        patient_id = create_hypertension_followup_patient(session)
        print(f"\n✅ 测试患者创建成功！")
        print(f"患者 ID: {patient_id}")
        return 0
        
    except Exception as e:
        print(f"\n❌ 错误：{e}")
        session.rollback()
        import traceback
        traceback.print_exc()
        return 1
        
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(main())
