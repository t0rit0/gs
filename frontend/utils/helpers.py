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
    # Current conversation state
    if 'current_conversation_id' not in st.session_state:
        st.session_state.current_conversation_id = None

    if 'current_patient_id' not in st.session_state:
        st.session_state.current_patient_id = None

    if 'messages' not in st.session_state:
        st.session_state.messages = []

    # Patient info for current conversation
    if 'current_patient_info' not in st.session_state:
        st.session_state.current_patient_info = {}

    # Conversation history list
    if 'conversation_history' not in st.session_state:
        st.session_state.conversation_history = []

    # Selected conversation from sidebar
    if 'selected_conversation_id' not in st.session_state:
        st.session_state.selected_conversation_id = None

    # Image panel states
    if 'image_panel_open' not in st.session_state:
        st.session_state.image_panel_open = False

    if 'uploaded_image' not in st.session_state:
        st.session_state.uploaded_image = None

    if 'image_analysis_report' not in st.session_state:
        st.session_state.image_analysis_report = None

    if 'thumbnail_visible' not in st.session_state:
        st.session_state.thumbnail_visible = False

    if 'last_processed_image' not in st.session_state:
        st.session_state.last_processed_image = None

    # Current page state
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "chat"

    # Selected patient for viewing conversations (in sidebar)
    if 'selected_patient_for_conversations' not in st.session_state:
        st.session_state.selected_patient_for_conversations = None

    # Backend client
    if 'backend_client' not in st.session_state:
        from frontend.utils.backend_client import BackendClient
        st.session_state.backend_client = BackendClient()


def reset_current_conversation():
    """Reset current conversation state (keep history list)"""
    st.session_state.current_conversation_id = None
    st.session_state.current_patient_id = None
    st.session_state.messages = []
    st.session_state.current_patient_info = {}
    # Reset image panel states
    st.session_state.image_panel_open = False
    st.session_state.uploaded_image = None
    st.session_state.image_analysis_report = None
    st.session_state.thumbnail_visible = False
    st.session_state.last_processed_image = None


def load_conversation(conversation_id: str, messages: list[dict], patient_info: dict):
    """Load a conversation into session state"""
    st.session_state.current_conversation_id = conversation_id
    st.session_state.messages = messages
    st.session_state.current_patient_info = patient_info
    if patient_info:
        st.session_state.current_patient_id = patient_info.get('patient_id')


def patient_create_form() -> dict[str, Any] | None:
    """
    Create patient input form for new patient creation

    Returns:
        Patient information dict or None
    """
    with st.form("patient_create_form"):
        st.subheader("新建患者 / Create New Patient")

        col1, col2 = st.columns(2)

        with col1:
            name = st.text_input("姓名 / Name*", placeholder="请输入患者姓名", key="new_patient_name")
            age = st.number_input("年龄 / Age*", min_value=0, max_value=150, value=30, key="new_patient_age")
            gender = st.selectbox("性别 / Gender*", ["男 / Male", "女 / Female", "其他 / Other"], key="new_patient_gender")

        with col2:
            phone = st.text_input("电话 / Phone", placeholder="联系电话", key="new_patient_phone")
            address = st.text_input("地址 / Address", placeholder="家庭地址", key="new_patient_address")

        submitted = st.form_submit_button("创建患者 / Create Patient", type="primary")

        if submitted and name:
            # Convert gender to English for backend
            gender_map = {"男 / Male": "male", "女 / Female": "female", "其他 / Other": "other"}
            return {
                "name": name,
                "age": age,
                "gender": gender_map[gender],
                "phone": phone or None,
                "address": address or None
            }
        elif submitted and not name:
            st.warning("请输入患者姓名 / Please enter patient name")

        return None


def patient_select_form(patients: list[dict]) -> dict[str, Any] | None:
    """
    Patient selection form for existing patients

    Args:
        patients: List of patient dicts

    Returns:
        Selected patient dict or None
    """
    if not patients:
        st.info("暂无患者记录 / No patient records")
        return None

    st.subheader("选择患者 / Select Patient")

    # Create patient options
    patient_options = {
        f"{p['name']} ({p['age']}岁, {p['gender']}) - {p['patient_id']}": p
        for p in patients
    }

    selected = st.selectbox(
        "选择已有患者 / Select existing patient",
        options=list(patient_options.keys()),
        key="patient_select"
    )

    if selected:
        return patient_options[selected]

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

        if patient_info.get("phone"):
            st.text(f"电话 / Phone: {patient_info['phone']}")

        if patient_info.get("address"):
            st.text(f"地址 / Address: {patient_info['address']}")

        if patient_info.get("patient_id"):
            st.text(f"患者ID / Patient ID: {patient_info['patient_id']}")


def display_conversation_list(conversations: list[dict], current_id: str | None = None):
    """
    Display conversation list in sidebar

    Args:
        conversations: List of conversation dicts
        current_id: Current conversation ID to highlight
    """
    if not conversations:
        st.info("暂无历史对话 / No conversation history")
        return

    st.markdown("### 历史对话 / History")

    for conv in reversed(conversations):  # Show newest first
        conv_id = conv.get('conversation_id')
        is_current = conv_id == current_id

        # Format conversation info
        target = conv.get('target', '诊断')
        status = conv.get('status', 'unknown')
        created_at = conv.get('created_at', '')
        message_count = conv.get('message_count', 0)

        if created_at:
            try:
                dt = datetime.fromisoformat(created_at.replace('Z', '+00:00'))
                time_str = dt.strftime("%m-%d %H:%M")
            except:
                time_str = created_at[:10]
        else:
            time_str = ""

        # Status emoji
        status_emoji = {
            "active": "💬",
            "completed": "✅",
            "abandoned": "⏹️"
        }.get(status, "💭")

        button_label = f"{status_emoji} {target} ({time_str})"

        if st.button(
            button_label,
            key=f"conv_{conv_id}",
            use_container_width=True,
            disabled=is_current,
            type="primary" if is_current else "secondary"
        ):
            return conv_id

    return None


def display_analysis_report(report: dict | None):
    """
    Display image analysis report

    Args:
        report: Analysis report dict or None
    """
    if not report:
        st.info("⏳ 等待 AI 分析结果... / Waiting for AI analysis...")
        return

    # Findings section
    with st.expander("🔍 检查发现 / Findings", expanded=True):
        if "findings" in report:
            findings = report["findings"]
            if isinstance(findings, list):
                for i, finding in enumerate(findings, 1):
                    st.markdown(f"**{i}.** {finding}")
            else:
                st.write(findings)

        if "recommendation" in report:
            st.info(f"💡 **建议 / Recommendation**: {report['recommendation']}")

    # AI interpretation
    with st.expander("🤖 AI 解读 / AI Interpretation", expanded=True):
        if "full_report" in report:
            st.write(report["full_report"])
        elif "findings" in report:
            findings = report["findings"]
            if isinstance(findings, list) and len(findings) > 0:
                for finding in findings:
                    st.write(f"• {finding}")
        elif isinstance(report, str):
            st.write(report)

    # Raw data
    if isinstance(report, dict):
        with st.expander("📄 原始数据 / Raw Data", expanded=False):
            st.json(report)
