#!/usr/bin/env python
"""
创建高血压测试患者

基于真实高血压病例的典型数据：
- 58 岁男性
- 2 期高血压（多次测量 140-150/90-96 mmHg）
- 合并症：糖尿病前期、高脂血症、睡眠呼吸暂停
- 症状：偶发头痛、头晕、轻度气短
- 用药：氨氯地平、赖诺普利、阿托伐他汀、二甲双胍
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


def create_hypertension_test_patient(session: Session) -> str:
    """
    创建高血压测试患者
    
    Returns:
        Patient ID
    """
    print("=" * 70)
    print("创建高血压测试患者")
    print("=" * 70)
    
    # 清理现有测试患者
    from backend.database.models import Patient, HealthMetricRecord
    existing = session.query(Patient).filter(Patient.name.like("高血压测试%")).all()
    for p in existing:
        session.delete(p)
    session.commit()
    print("✓ 已清理旧测试数据")
    
    # ============================================
    # 1. 创建患者基本信息
    # ============================================
    print("\n[1/4] 创建患者基本信息...")
    
    patient = patient_crud.create(session, PatientCreate(
        name="高血压测试患者 - 张三",
        age=58,
        gender="male",
        phone="13800138058",
        address="北京市朝阳区建国路 88 号",
        occupation="行政管理员",
        # BMI: 28.4 (超重)
        height=175,  # cm
        weight=87,   # kg
        
        # 既往病史
        medical_history=[
            {
                "condition": "高血压病 2 级",
                "diagnosis_date": "2025-01-15T00:00:00",
                "status": "chronic",
                "notes": "原发性高血压，确诊时血压 142/92 mmHg"
            },
            {
                "condition": "糖尿病前期",
                "diagnosis_date": "2025-01-15T00:00:00",
                "status": "active",
                "notes": "空腹血糖受损，HbA1c 5.9%"
            },
            {
                "condition": "高脂血症",
                "diagnosis_date": "2025-01-15T00:00:00",
                "status": "active",
                "notes": "总胆固醇 215 mg/dL, LDL 138 mg/dL"
            },
            {
                "condition": "阻塞性睡眠呼吸暂停",
                "diagnosis_date": "2023-06-15T00:00:00",
                "status": "chronic",
                "notes": "使用 CPAP 治疗"
            },
            {
                "condition": "膝骨关节炎",
                "diagnosis_date": "2022-03-10T00:00:00",
                "status": "chronic",
                "notes": "双膝轻度退行性变"
            }
        ],
        
        # 家族史
        family_history=[
            {
                "relation": "父亲",
                "condition": "高血压、心肌梗死",
                "age_at_diagnosis": 52,
                "notes": "61 岁发生心梗"
            },
            {
                "relation": "母亲",
                "condition": "2 型糖尿病",
                "age_at_diagnosis": 58,
                "notes": ""
            },
            {
                "relation": "哥哥",
                "condition": "高血压",
                "age_at_diagnosis": 55,
                "notes": ""
            }
        ],
        
        # 过敏史
        allergies=[
            {
                "allergen": "青霉素",
                "severity": "moderate",
                "reaction": "皮疹",
                "diagnosed_date": "2010-05-10T00:00:00"
            }
        ],
        
        # 用药史
        medications=[
            {
                "medication_name": "氨氯地平",
                "dosage": "5mg",
                "frequency": "每日一次",
                "start_date": "2025-01-15T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "钙通道阻滞剂"
            },
            {
                "medication_name": "赖诺普利",
                "dosage": "10mg",
                "frequency": "每日一次",
                "start_date": "2025-02-05T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "ACE 抑制剂"
            },
            {
                "medication_name": "阿托伐他汀",
                "dosage": "20mg",
                "frequency": "每晚一次",
                "start_date": "2025-01-15T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "降胆固醇"
            },
            {
                "medication_name": "二甲双胍",
                "dosage": "500mg",
                "frequency": "每日两次",
                "start_date": "2025-01-15T00:00:00",
                "prescribing_doctor": "李医生",
                "notes": "糖尿病前期管理"
            }
        ],
        
        # 生活方式
        lifestyle={
            "smoking_status": "never",
            "alcohol_consumption": "偶尔，每周 2-3 瓶啤酒",
            "exercise_frequency": "每周 2-3 次，每次 20 分钟散步",
            "diet_notes": "高钠饮食（估计 3500-4000mg/天），水果蔬菜摄入不足",
            "sleep_quality": "使用 CPAP 后改善",
            "bmi": 28.4  # BMI 存储在 lifestyle 中
        }
    ))
    
    print(f"✓ 患者创建成功：{patient.patient_id}")
    print(f"  姓名：{patient.name}")
    print(f"  年龄：{patient.age}岁")
    print(f"  性别：{patient.gender}")
    
    # ============================================
    # 2. 创建血压记录（多次测量）
    # ============================================
    print("\n[2/4] 创建血压记录...")
    
    now = datetime.now()
    bp_records = [
        # 初次就诊 - 确诊
        {"date": now - timedelta(days=70), "value": "142/92", "notes": "初次就诊，确诊高血压"},
        # 一周后随访
        {"date": now - timedelta(days=63), "value": "138/88", "notes": "开始服用氨氯地平"},
        # 家庭监测
        {"date": now - timedelta(days=49), "value": "145/94", "notes": "家庭自测，早晨测量"},
        # 再次随访
        {"date": now - timedelta(days=35), "value": "151/96", "notes": "加用赖诺普利"},
        # 最近随访
        {"date": now - timedelta(days=21), "value": "136/85", "notes": "血压有所控制"},
        # 最新测量
        {"date": now - timedelta(days=7), "value": "140/90", "notes": "常规随访"},
    ]
    
    for record in bp_records:
        bp_record = MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name="Blood Pressure",
            value=record["value"],
            measured_at=record["date"],
            context=record["notes"]
        )
        print(f"  ✓ BP: {record['value']} @ {record['date'].strftime('%Y-%m-%d')}")
    
    # ============================================
    # 3. 创建其他健康指标
    # ============================================
    print("\n[3/4] 创建其他健康指标...")
    
    # 生命体征
    metrics = [
        # 心率
        {"name": "Heart Rate", "value": "78", "unit": "bpm", "date": now - timedelta(days=70), "notes": "静息心率"},
        {"name": "Heart Rate", "value": "72", "unit": "bpm", "date": now - timedelta(days=7), "notes": "静息心率，有所改善"},
        
        # 血糖
        {"name": "Glucose", "value": "108", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "空腹血糖，偏高"},
        {"name": "Glucose", "value": "102", "unit": "mg/dL", "date": now - timedelta(days=7), "notes": "空腹血糖，有所改善"},
        
        # 糖化血红蛋白
        {"name": "HbA1c", "value": "5.9", "unit": "%", "date": now - timedelta(days=70), "notes": "糖尿病前期范围"},
        
        # 血脂
        {"name": "Total Cholesterol", "value": "215", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "边界偏高"},
        {"name": "LDL Cholesterol", "value": "138", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "偏高"},
        {"name": "HDL Cholesterol", "value": "42", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "正常"},
        {"name": "Triglycerides", "value": "175", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "偏高"},
        
        # 肾功能
        {"name": "Creatinine", "value": "1.1", "unit": "mg/dL", "date": now - timedelta(days=70), "notes": "正常"},
        {"name": "eGFR", "value": "78", "unit": "mL/min/1.73m²", "date": now - timedelta(days=70), "notes": "轻度下降"},
        
        # 电解质
        {"name": "Potassium", "value": "4.2", "unit": "mEq/L", "date": now - timedelta(days=70), "notes": "正常"},
        {"name": "Sodium", "value": "140", "unit": "mEq/L", "date": now - timedelta(days=70), "notes": "正常"},
        
        # 体重
        {"name": "Weight", "value": "87", "unit": "kg", "date": now - timedelta(days=70), "notes": "初诊体重"},
        {"name": "Weight", "value": "85.5", "unit": "kg", "date": now - timedelta(days=7), "notes": "减轻 1.5kg"},
        
        # 收缩压/舒张压（单独记录）
        {"name": "Systolic BP", "value": "140", "unit": "mmHg", "date": now - timedelta(days=7), "notes": "最新收缩压"},
        {"name": "Diastolic BP", "value": "90", "unit": "mmHg", "date": now - timedelta(days=7), "notes": "最新舒张压"},
    ]
    
    for metric in metrics:
        MetricCRUD.create_record(
            db=session,
            patient_id=patient.patient_id,
            metric_name=metric["name"],
            value=metric["value"],
            unit=metric["unit"],
            measured_at=metric["date"],
            context=metric["notes"]
        )
    
    print(f"  ✓ 创建了 {len(metrics)} 项健康指标")
    
    # ============================================
    # 4. 创建症状记录
    # ============================================
    print("\n[4/4] 创建症状记录...")
    
    symptoms = [
        {
            "symptom": "头痛",
            "description": "轻度头痛，每周 2-3 次，多在早晨",
            "status": "active",
            "severity": "mild",
            "frequency": "2-3 times/week",
            "onset_date": (now - timedelta(days=90)).strftime('%Y-%m-%d')
        },
        {
            "symptom": "头晕",
            "description": "快速站立时偶发头晕",
            "status": "active",
            "severity": "mild",
            "frequency": "occasional",
            "onset_date": (now - timedelta(days=60)).strftime('%Y-%m-%d')
        },
        {
            "symptom": "气短",
            "description": "爬 2 层以上楼梯时轻度气短",
            "status": "active",
            "severity": "mild",
            "frequency": "on exertion",
            "onset_date": (now - timedelta(days=45)).strftime('%Y-%m-%d')
        },
        {
            "symptom": "疲劳",
            "description": "下午感到疲劳，休息后可缓解",
            "status": "active",
            "severity": "mild",
            "frequency": "daily",
            "onset_date": (now - timedelta(days=30)).strftime('%Y-%m-%d')
        },
        {
            "symptom": "心悸",
            "description": "紧张时偶感心悸",
            "status": "active",
            "severity": "mild",
            "frequency": "occasional",
            "onset_date": (now - timedelta(days=20)).strftime('%Y-%m-%d')
        },
        {
            "symptom": "睡眠质量差",
            "description": "使用 CPAP 前睡眠中断",
            "status": "resolved",
            "severity": "moderate",
            "frequency": "improved with CPAP",
            "onset_date": (now - timedelta(days=365)).strftime('%Y-%m-%d')
        }
    ]
    
    for symptom in symptoms:
        patient_crud.add_symptom(
            db=session,
            patient_id=patient.patient_id,
            symptom=symptom["symptom"],
            description=symptom["description"],
            status=symptom["status"]
        )
        print(f"  ✓ 症状：{symptom['symptom']} ({symptom['status']})")
    
    # 提交所有更改
    session.commit()
    
    # ============================================
    # 总结
    # ============================================
    print("\n" + "=" * 70)
    print("✅ 高血压测试患者创建完成")
    print("=" * 70)
    print(f"\n患者 ID: {patient.patient_id}")
    print(f"姓名：{patient.name}")
    print(f"年龄：{patient.age}岁，性别：{patient.gender}")
    print(f"BMI: 28.4 (超重)")
    
    print("\n📋 诊断摘要:")
    print("  • 高血压病 2 级（确诊 2025-01-15）")
    print("  • 糖尿病前期")
    print("  • 高脂血症")
    print("  • 阻塞性睡眠呼吸暂停")
    print("  • 膝骨关节炎")
    
    print("\n💊 当前用药:")
    print("  • 氨氯地平 5mg qd")
    print("  • 赖诺普利 10mg qd")
    print("  • 阿托伐他汀 20mg qn")
    print("  • 二甲双胍 500mg bid")
    
    print("\n📊 血压趋势:")
    print("  • 初诊：142/92 mmHg")
    print("  • 最高：151/96 mmHg")
    print("  • 最新：140/90 mmHg")
    print("  • 目标：<130/80 mmHg")
    
    print("\n🔍 症状:")
    print("  • 头痛（轻度，每周 2-3 次）")
    print("  • 头晕（偶发）")
    print("  • 气短（活动时）")
    print("  • 疲劳（每日）")
    print("  • 心悸（偶发）")
    
    print("\n" + "=" * 70)
    print(f"提示：使用此患者 ID 进行测试：{patient.patient_id}")
    print("=" * 70)
    
    return patient.patient_id


def main():
    """主函数"""
    session = SessionLocal()
    
    try:
        patient_id = create_hypertension_test_patient(session)
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
