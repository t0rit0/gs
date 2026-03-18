"""
Medication Management Components for Streamlit Frontend

Week 7+ Implementation
"""

import streamlit as st
import pandas as pd
from datetime import date, datetime, time
import requests


def render_medications_tab(patient_id: str, api_base_url: str):
    """
    渲染用药管理标签页
    
    功能:
    - 当前用药列表
    - 创建用药卡片
    - 今日用药计划
    - 用药统计
    """
    st.markdown("### 💊 用药管理 / Medications")
    
    # 子标签页
    med_tab1, med_tab2, med_tab3 = st.tabs([
        "当前用药",
        "今日用药",
        "📊 统计"
    ])
    
    with med_tab1:
        render_medication_cards(patient_id, api_base_url)
    
    with med_tab2:
        render_today_schedules(patient_id, api_base_url)
    
    with med_tab3:
        render_medication_stats(patient_id, api_base_url)


def render_medication_cards(patient_id: str, api_base_url: str):
    """渲染用药卡片列表"""
    
    st.markdown("#### 当前用药卡片")
    
    # 获取用药卡片
    try:
        response = requests.get(
            f"{api_base_url}/api/patients/{patient_id}/medications",
            params={"status": "active"}
        )
        cards = response.json()
    except Exception as e:
        st.error(f"加载失败：{str(e)}")
        cards = []
    
    if cards:
        for card in cards:
            display_medication_card(card, api_base_url)
    else:
        st.info("暂无当前用药记录")
    
    # 操作按钮
    col1, col2 = st.columns(2)
    with col1:
        if st.button("➕ 创建用药卡片", use_container_width=True):
            st.session_state.show_medication_form = True
    with col2:
        if st.button("📥 导入 CSV", use_container_width=True):
            st.session_state.show_import_form = True
    
    # 创建表单
    if st.session_state.get("show_medication_form"):
        display_medication_card_form(patient_id, api_base_url)
    
    # 导入表单
    if st.session_state.get("show_import_form"):
        display_medication_import_form(patient_id, api_base_url)


def display_medication_card(card: dict, api_base_url: str):
    """显示单个用药卡片"""
    
    with st.container():
        col1, col2, col3 = st.columns([3, 2, 1])
        
        with col1:
            # Get dosage from sig
            dosage = card.get('sig', {}).get('dose', '')
            dose_unit = card.get('sig', {}).get('dose_unit', '')
            dosage_str = f"{dosage}{dose_unit}" if dosage else ""
            
            st.markdown(f"**{card['drug_name']}** {dosage_str}")
            st.caption(f"频率：{card['sig'].get('frequency', '')}")
            if card.get('instructions'):
                st.caption(f"医嘱：{card['instructions']}")
        
        with col2:
            st.caption(f"处方日期：{card['prescribed_date'][:10] if card.get('prescribed_date') else ''}")
            if card.get('end_date'):
                st.caption(f"结束日期：{card['end_date'][:10]}")
        
        with col3:
            if st.button("⏹️ 停药", key=f"stop_{card['card_id']}"):
                st.session_state.stopping_card = card
        
        st.divider()


def display_medication_card_form(patient_id: str, api_base_url: str):
    """显示用药卡片创建表单"""
    
    st.markdown("#### 📝 创建用药卡片")
    
    with st.form("medication_card_form"):
        col1, col2 = st.columns(2)
        
        with col1:
            drug_name = st.text_input("药品名称 *", placeholder="如：阿莫西林胶囊")
            dosage = st.text_input("剂量 *", placeholder="如：0.5")
            dose_unit = st.selectbox("剂量单位", options=["g", "mg", "ml"], index=1)
            prescribed_date = st.date_input("处方日期", value=date.today())
        
        with col2:
            frequency = st.selectbox(
                "频率 *",
                options=["一天一次", "一天两次", "一天三次", "每 8 小时", "按需服用"]
            )
            route = st.selectbox("给药途径", options=["口服", "注射", "外用"], index=0)
            duration_days = st.number_input("疗程天数", min_value=1, value=5)
            instructions = st.text_area("医嘱", placeholder="如：饭后服用")
        
        submitted = st.form_submit_button("💾 保存记录")
        
        if submitted:
            if not all([drug_name, dosage, frequency]):
                st.error("请填写必需字段")
            else:
                try:
                    sig = {
                        "dose": float(dosage),
                        "dose_unit": dose_unit,
                        "route": route,
                        "frequency": frequency,
                        "duration_days": int(duration_days)
                    }
                    
                    response = requests.post(
                        f"{api_base_url}/api/patients/{patient_id}/medications",
                        json={
                            "drug_name": drug_name,
                            "sig": sig,
                            "instructions": instructions,
                            "prescribed_date": prescribed_date.isoformat()
                        }
                    )
                    
                    if response.status_code == 201:
                        st.success("✅ 用药卡片已创建")
                        st.session_state.show_medication_form = False
                        st.rerun()
                    else:
                        st.error(f"创建失败：{response.text}")
                except Exception as e:
                    st.error(f"创建失败：{str(e)}")


def display_medication_import_form(patient_id: str, api_base_url: str):
    """显示 CSV 导入表单"""
    
    st.markdown("#### 📥 导入用药卡片")
    
    # 下载模板
    template_csv = """drug_name,dose,dose_unit,frequency,duration_days,instructions
阿莫西林胶囊，0.5,g，一天三次，5，饭后服用
布洛芬，200,mg，按需服用，0，疼痛时服用"""
    
    st.download_button(
        label="📥 下载模板 CSV",
        data=template_csv,
        file_name="medication_template.csv",
        mime="text/csv"
    )
    
    uploaded_file = st.file_uploader("上传 CSV 文件", type=["csv"])
    
    if uploaded_file:
        # 预览
        df = pd.read_csv(uploaded_file)
        st.dataframe(df.head())
        
        if st.button("📥 导入"):
            try:
                files = {"file": uploaded_file.getvalue()}
                response = requests.post(
                    f"{api_base_url}/api/patients/{patient_id}/medications/import",
                    files=files
                )
                
                if response.status_code == 200:
                    result = response.json()
                    st.success(f"✅ 导入完成：{result['imported']}条记录")
                    if result['skipped'] > 0:
                        st.warning(f"跳过：{result['skipped']}条")
                    st.session_state.show_import_form = False
                    st.rerun()
            except Exception as e:
                st.error(f"导入失败：{str(e)}")


def render_today_schedules(patient_id: str, api_base_url: str):
    """渲染今日用药计划"""
    
    st.markdown("#### 💊 今日用药计划")
    
    # Get medication cards for reference
    medication_cards = {}
    try:
        cards_response = requests.get(
            f"{api_base_url}/api/patients/{patient_id}/medications",
            params={"status": "all"}
        )
        for card in cards_response.json():
            medication_cards[card['card_id']] = card
    except:
        pass
    
    # Get today's schedules
    try:
        response = requests.get(
            f"{api_base_url}/api/patients/{patient_id}/schedules/today"
        )
        schedules = response.json()
    except Exception as e:
        st.error(f"加载失败：{str(e)}")
        schedules = []
    
    if schedules:
        for schedule in schedules:
            display_schedule_item(schedule, api_base_url, medication_cards)
    else:
        st.info("今日无用药计划")


def display_schedule_item(schedule: dict, api_base_url: str, medication_cards: dict = None):
    """显示单个用药计划项"""
    
    # Get medication info from card
    card_id = schedule['card_id']
    med_info = ""
    
    if medication_cards and card_id in medication_cards:
        card = medication_cards[card_id]
        drug_name = card.get('drug_name', '')
        dosage = card.get('sig', {}).get('dose', '')
        dose_unit = card.get('sig', {}).get('dose_unit', '')
        frequency = card.get('sig', {}).get('frequency', '')
        med_info = f"{drug_name} {dosage}{dose_unit} ({frequency})"
    else:
        med_info = f"卡片 ID: {card_id[:8]}..."
    
    col1, col2, col3 = st.columns([3, 2, 1])
    
    with col1:
        st.markdown(f"**{schedule['scheduled_time'][:5]}**")
        st.caption(med_info)
    
    with col2:
        if schedule['status'] == 'completed':
            st.success(f"✅ 已服 {schedule['taken_at'][11:16] if schedule.get('taken_at') else ''}")
        elif schedule['status'] == 'pending':
            st.warning("⏳ 待服药")
        else:
            st.error("❌ 漏服")
    
    with col3:
        if schedule['status'] == 'pending':
            if st.button("我吃了", key=f"take_{schedule['schedule_id']}"):
                confirm_medication(schedule['schedule_id'], api_base_url)


def confirm_medication(schedule_id: str, api_base_url: str):
    """确认服药"""
    try:
        # 需要从父组件获取 patient_id
        response = requests.post(
            f"{api_base_url}/api/patients/TEST-PATIENT/schedules/{schedule_id}/confirm",
            json={}
        )
        
        if response.status_code == 200:
            st.success("✅ 已确认服药")
            st.rerun()
        else:
            st.error(f"确认失败：{response.text}")
    except Exception as e:
        st.error(f"确认失败：{str(e)}")


def render_medication_stats(patient_id: str, api_base_url: str):
    """渲染用药统计"""
    
    st.markdown("#### 📊 用药统计")
    
    days = st.slider("统计天数", min_value=7, max_value=365, value=30)
    
    try:
        response = requests.get(
            f"{api_base_url}/api/patients/{patient_id}/schedules/history/summary",
            params={"days": days}
        )
        stats = response.json()
    except Exception as e:
        st.error(f"加载失败：{str(e)}")
        return
    
    # 显示统计
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("总计划数", stats.get('total_schedules', 0))
    
    with col2:
        st.metric("已完成", stats.get('completed', 0))
    
    with col3:
        st.metric("漏服", stats.get('missed', 0))
    
    with col4:
        st.metric("完成率", f"{stats.get('completion_rate', 0)}%")
