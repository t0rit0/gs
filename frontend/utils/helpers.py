# Helper utilities

from datetime import datetime
from typing import Any

import streamlit as st


def format_timestamp(timestamp: str) -> str:
    """Format timestamp for display"""
    try:
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except (ValueError, TypeError):
        return timestamp


def display_message(role: str, content: str, timestamp: str | None = None):
    """
    Display a chat message with proper styling

    Args:
        role: Message role ('human' or 'ai')
        content: Message content
        timestamp: Optional timestamp
    """
    if role == "human":
        with st.chat_message("user"):
            st.write(content)
            if timestamp:
                st.caption(f"发送时间: {format_timestamp(timestamp)}")
    else:
        with st.chat_message("assistant"):
            st.write(content)
            if timestamp:
                st.caption(f"回复时间: {format_timestamp(timestamp)}")


def display_image_with_metadata(image_path: str, metadata: dict[str, Any] | None = None):
    """
    Display an image with metadata

    Args:
        image_path: Path to image
        metadata: Optional metadata dict
    """
    st.image(image_path, caption="上传的医学影像", use_container_width=True)
    if metadata:
        with st.expander("影像分析结果"):
            st.json(metadata)


def initialize_session_state():
    """Initialize Streamlit session state variables"""
    if 'conversation_id' not in st.session_state:
        st.session_state.conversation_id = None

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    if 'patient_info' not in st.session_state:
        st.session_state.patient_info = {}

    if 'current_patient_id' not in st.session_state:
        st.session_state.current_patient_id = None


def reset_conversation():
    """Reset conversation state"""
    st.session_state.conversation_id = None
    st.session_state.messages = []


def patient_info_form() -> dict[str, Any]:
    """
    Create patient information input form

    Returns:
        Patient information dict
    """
    with st.form("patient_info_form"):
        st.subheader("患者信息 / Patient Information")

        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("姓名 / Name*", placeholder="请输入患者姓名")
            age = st.number_input("年龄 / Age*", min_value=0, max_value=150, value=30)
            gender = st.selectbox("性别 / Gender*", ["男", "女", "其他"])

        with col2:
            contact = st.text_input("联系方式 / Contact", placeholder="电话或邮箱")
            patient_id = st.text_input("患者ID / Patient ID", placeholder="留空自动生成")

        medical_history = st.text_area(
            "既往病史 / Medical History",
            placeholder="请输入既往病史、过敏史等...",
            height=100
        )

        submitted = st.form_submit_button("开始问诊 / Start Consultation", type="primary")

        if submitted and name:
            return {
                "name": name,
                "age": age,
                "gender": gender,
                "contact": contact or None,
                "patient_id": patient_id or None,
                "medical_history": medical_history or None
            }

        return None


def display_patient_info(patient_info: dict[str, Any]):
    """
    Display patient information in a formatted way

    Args:
        patient_info: Patient information dict
    """
    with st.expander("患者信息 / Patient Information", expanded=True):
        col1, col2, col3 = st.columns(3)

        with col1:
            st.metric("姓名 / Name", patient_info.get("name", "未知"))

        with col2:
            st.metric("年龄 / Age", str(patient_info.get("age", "未知")))

        with col3:
            st.metric("性别 / Gender", patient_info.get("gender", "未知"))

        if patient_info.get("contact"):
            st.text(f"联系方式 / Contact: {patient_info['contact']}")

        if patient_info.get("patient_id"):
            st.text(f"患者ID: {patient_info['patient_id']}")

        if patient_info.get("medical_history"):
            st.text_area("既往病史 / Medical History",
                        patient_info['medical_history'],
                        height=80,
                        disabled=True)
