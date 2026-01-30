# Chat Page - Medical Assistant with Conversation History Sidebar

import base64
import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.config import MAX_IMAGE_SIZE_MB, SUPPORTED_IMAGE_TYPES
from frontend.utils.helpers import (
    display_message,
    display_patient_info,
    display_conversation_list,
    display_analysis_report,
    patient_create_form,
    patient_select_form,
    reset_current_conversation,
    load_conversation,
    format_timestamp,
)


def image_to_base64(image_file) -> str:
    """Convert uploaded image file to base64 string"""
    image_bytes = image_file.getvalue()
    base64_bytes = base64.b64encode(image_bytes)
    base64_string = base64_bytes.decode('utf-8')
    mime_type = image_file.type
    return f"data:{mime_type};base64,{base64_string}"


def sidebar():
    """Sidebar with conversation history and actions"""
    with st.sidebar:
        st.title("💬 对话问诊 / Consultation")
        st.markdown("---")

        client = st.session_state.backend_client

        # Patient selection section
        if not st.session_state.get('selected_patient_for_conversations'):
            st.markdown("### 👤 选择患者 / Select Patient")

            # Get all patients
            try:
                patients = client.list_patients(limit=100)
            except Exception as e:
                st.error(f"加载患者失败 / Failed to load patients: {str(e)}")
                patients = []

            # Tab for existing or new patient
            tab1, tab2 = st.tabs(["已有患者 / Existing", "新建患者 / New"])

            with tab1:
                selected_patient = patient_select_form(patients)
                if selected_patient:
                    if st.button("查看对话 / View Conversations", type="primary", use_container_width=True, key="view_conv_btn"):
                        st.session_state.selected_patient_for_conversations = selected_patient
                        st.rerun()

            with tab2:
                new_patient = patient_create_form()
                if new_patient:
                    try:
                        created_patient = client.create_patient(new_patient)
                        st.success(f"✅ 患者已创建 / Patient created: {created_patient['name']}")
                        st.session_state.selected_patient_for_conversations = created_patient
                        st.rerun()
                    except Exception as e:
                        st.error(f"创建失败 / Creation failed: {str(e)}")

        else:
            # Show selected patient with their conversation history
            patient = st.session_state.selected_patient_for_conversations

            # Patient info
            st.markdown("### 👤 当前患者 / Current Patient")
            st.info(f"**{patient.get('name')}** ({patient.get('age')}岁, {patient.get('gender')})")

            if st.button("更换患者 / Change Patient", use_container_width=True):
                st.session_state.selected_patient_for_conversations = None
                st.session_state.current_conversation_id = None
                st.session_state.current_patient_id = None
                st.session_state.current_patient_info = {}
                st.session_state.messages = []
                st.rerun()

            st.markdown("---")

            # Load and display conversation history
            try:
                conversations = client.get_patient_conversations(
                    patient['patient_id'],
                    limit=50
                )

                if conversations:
                    st.markdown("### 📋 历史对话 / Conversation History")

                    # Sort conversations by created_at (newest first)
                    conversations_sorted = sorted(
                        conversations,
                        key=lambda x: x.get('created_at', ''),
                        reverse=True
                    )

                    for conv in conversations_sorted:
                        conv_id = conv.get('conversation_id')
                        is_current = conv_id == st.session_state.current_conversation_id

                        # Format conversation info
                        target = conv.get('target', '诊断')
                        status = conv.get('status', 'unknown')
                        created_at = conv.get('created_at', '')
                        message_count = conv.get('message_count', 0)

                        if created_at:
                            try:
                                from datetime import datetime
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

                        # Create expandable section for each conversation
                        with st.expander(
                            f"{status_emoji} {target} ({time_str}) - {message_count}条消息",
                            expanded=is_current
                        ):
                            st.caption(f"会话ID / ID: `{conv_id[:12]}...`")
                            st.caption(f"状态 / Status: {status}")

                            col1, col2 = st.columns(2)

                            with col1:
                                if st.button(
                                    "继续对话 / Continue",
                                    key=f"continue_{conv_id}",
                                    type="primary" if is_current else "secondary",
                                    use_container_width=True,
                                    disabled=is_current
                                ):
                                    # Load the conversation
                                    try:
                                        messages = client.get_conversation_messages(conv_id)

                                        # Convert messages to display format
                                        display_messages = [
                                            {
                                                "role": msg["role"],
                                                "content": msg["content"],
                                                "timestamp": msg["timestamp"]
                                            }
                                            for msg in messages
                                        ]

                                        load_conversation(conv_id, display_messages, patient)
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"加载对话失败 / Failed to load: {str(e)}")

                            with col2:
                                if st.button(
                                    "查看详情 / View",
                                    key=f"view_detail_{conv_id}",
                                    use_container_width=True
                                ):
                                    # Show conversation details (could be expanded in future)
                                    st.json(conv)

                    st.markdown("---")

                    # New conversation button
                    st.markdown("### ➕ 开始新对话 / Start New Conversation")
                    if st.button("新建对话 / Create New", type="primary", use_container_width=True, key="new_conv_btn"):
                        # Reset for new conversation
                        reset_current_conversation()
                        st.session_state.selected_patient = patient
                        st.rerun()

                else:
                    # No conversations for this patient
                    st.info("📭 该患者暂无历史对话 / No conversation history")

                    st.markdown("---")
                    st.markdown("### ➕ 开始新对话 / Start New Conversation")
                    if st.button("创建第一个对话 / Create First", type="primary", use_container_width=True):
                        reset_current_conversation()
                        st.session_state.selected_patient = patient
                        st.rerun()

            except Exception as e:
                st.error(f"加载历史对话失败 / Failed to load history: {str(e)}")


def display_image_panel():
    """Display the medical image with analysis report in left panel"""
    if not st.session_state.uploaded_image:
        return

    with st.container():
        # Panel header with close button
        col1, col2 = st.columns([4, 1])
        with col1:
            st.markdown("### 📷 医学影像分析 / Medical Image Analysis")
        with col2:
            if st.button("✕ 关闭 / Close", key="close_image_panel", use_container_width=True):
                st.session_state.image_panel_open = False
                st.session_state.thumbnail_visible = True
                st.rerun()

        st.markdown("---")

        # Image display
        st.image(
            st.session_state.uploaded_image,
            use_container_width=True,
            caption="上传的医学影像 / Uploaded Medical Image"
        )

        # Analysis report section
        st.markdown("### 📋 分析报告 / Analysis Report")
        display_analysis_report(st.session_state.image_analysis_report)


def display_thumbnail():
    """Display a clickable thumbnail to reopen the image panel"""
    if st.session_state.uploaded_image and st.session_state.thumbnail_visible:
        st.markdown("---")
        col1, col2 = st.columns([1, 5])

        with col1:
            st.image(
                st.session_state.uploaded_image,
                width=100,
                caption="点击查看 / Click to view"
            )

        with col2:
            if st.button("📷 打开医学影像 / Open Medical Image", key="reopen_image_panel"):
                st.session_state.image_panel_open = True
                st.session_state.thumbnail_visible = False
                st.rerun()


def chat_page():
    """Main chat/consultation page"""

    # Initialize conversation if selected patient is set
    if hasattr(st.session_state, 'selected_patient') and st.session_state.selected_patient:
        if not st.session_state.current_conversation_id:
            patient = st.session_state.selected_patient

            # Create new conversation
            client = st.session_state.backend_client
            try:
                with st.spinner("正在初始化问诊会话 / Initializing consultation..."):
                    result = client.create_conversation(
                        patient_id=patient['patient_id'],
                        target="Hypertension diagnosis"
                    )

                    st.session_state.current_conversation_id = result['conversation_id']
                    st.session_state.current_patient_id = patient['patient_id']
                    st.session_state.current_patient_info = patient

                    # Add welcome message
                    welcome_msg = result.get('ai_message', f"您好，{patient['name']}。我是 Dr.Hyper，您的高血压专科AI助手。")
                    st.session_state.messages.append({
                        "role": "ai",
                        "content": welcome_msg
                    })

                    # Clear selected patient to avoid re-initialization
                    st.session_state.selected_patient = None
                    st.rerun()

            except Exception as e:
                st.error(f"初始化失败 / Initialization failed: {str(e)}")

    # Render sidebar
    sidebar()

    # Main content area
    if not st.session_state.current_conversation_id:
        st.info("👈 请从侧边栏选择患者以开始问诊 / Please select a patient from the sidebar to start consultation")

        # Display quick instructions
        st.markdown("""
        ### 📋 使用说明 / Instructions

        1. **选择患者 / Select Patient**: 从左侧侧边栏选择已有患者或创建新患者
        2. **开始对话 / Start Conversation**: 选择患者后自动创建新对话，或从历史对话中选择
        3. **发送消息 / Send Message**: 输入问题或症状，AI 将协助诊断
        4. **上传影像 / Upload Image**: 支持上传医学影像进行 AI 分析

        ---
        ### Quick Instructions

        1. **Select Patient**: Choose an existing patient or create a new one from the sidebar
        2. **Start Conversation**: A new conversation is created automatically, or select from history
        3. **Send Message**: Enter your symptoms or questions for AI assistance
        4. **Upload Image**: Medical images can be uploaded for AI analysis
        """)
        return

    # Active conversation
    patient_info = st.session_state.current_patient_info

    # Split view if image panel is open
    if st.session_state.image_panel_open:
        col_left, col_right = st.columns([1, 1])
        with col_left:
            display_image_panel()
        with col_right:
            display_chat_interface(patient_info)
    else:
        display_chat_interface(patient_info)

    # Show thumbnail at the bottom when panel is closed
    display_thumbnail()


def display_chat_interface(patient_info: dict):
    """Display the chat interface"""

    # Display patient info
    display_patient_info(patient_info)

    # Chat messages
    st.markdown("### 💭 对话记录 / Conversation History")

    # Display message history
    for msg in st.session_state.messages:
        display_message(msg["role"], msg["content"], msg.get("timestamp"))

    st.markdown("---")

    # Input section with image upload
    col1, col2 = st.columns([2, 1])

    with col1, st.form("chat_form", clear_on_submit=True):
        user_input = st.text_area(
            "消息输入 / Message Input",
            placeholder="请输入您的症状、问题或回复... / Enter your symptoms, questions, or responses...",
            height=100,
            label_visibility="collapsed"
        )
        submit = st.form_submit_button("发送 / Send", type="primary", use_container_width=True)

    with col2:
        st.markdown("### 📷")

        if st.session_state.get('uploaded_image') and st.session_state.get('last_processed_image'):
            st.info("ℹ️ 图片已上传 / Image uploaded")

        uploaded_file = st.file_uploader(
            "医学影像上传 / Medical Image Upload",
            type=SUPPORTED_IMAGE_TYPES,
            help=f"支持: {', '.join(SUPPORTED_IMAGE_TYPES)} (最大 {MAX_IMAGE_SIZE_MB}MB)",
            label_visibility="collapsed",
            key="image_uploader"
        )

    # Handle form submission
    if submit:
        # Process image if uploaded and it's a NEW file
        base64_image = None
        image_attached = False

        if uploaded_file:
            current_file_name = uploaded_file.name
            last_processed_file = st.session_state.get('last_processed_image', None)

            if current_file_name != last_processed_file:
                image_attached = True
                st.session_state.uploaded_image = uploaded_file
                base64_image = image_to_base64(uploaded_file)
                st.session_state.last_processed_image = current_file_name

        # Prepare message content
        if user_input and image_attached:
            message_content = f"{user_input} [已上传医学影像 / Medical image attached]"
        elif user_input:
            message_content = user_input
        elif image_attached:
            message_content = "请分析这张医学影像 / Please analyze this medical image"
        else:
            st.warning("请输入消息或上传新图片 / Please enter a message or upload a new image")
            st.rerun()
            return

        # Add user message
        st.session_state.messages.append({
            "role": "human",
            "content": message_content
        })

        # Get AI response
        spinner_text = "正在分析医学影像... / Analyzing medical image..." if base64_image else "AI 正在思考... / AI is thinking..."
        with st.spinner(spinner_text):
            try:
                client = st.session_state.backend_client

                images = [base64_image] if base64_image else None
                result = client.chat(
                    conversation_id=st.session_state.current_conversation_id,
                    message=message_content,
                    images=images
                )

                ai_response = result.get("ai_message", "抱歉，我现在无法回复。")
                accomplish = result.get("accomplish", False)
                analysis_report = result.get("analysis_report")

                # Add AI response
                st.session_state.messages.append({
                    "role": "ai",
                    "content": ai_response
                })

                # Store analysis report if image was analyzed
                if base64_image:
                    if analysis_report:
                        # Only show image panel if backend returned a proper analysis report
                        st.session_state.image_analysis_report = analysis_report
                        st.session_state.image_panel_open = True
                        st.session_state.thumbnail_visible = False
                    else:
                        # No structured analysis report from backend
                        # Don't create a fake one - just acknowledge the image was uploaded
                        st.session_state.image_analysis_report = None
                        st.session_state.image_panel_open = False
                        st.info("📷 影像已上传，等待AI分析... / Image uploaded, waiting for AI analysis...")

                if accomplish:
                    st.success("✅ 诊断完成 / Diagnosis Completed")

                st.rerun()

            except Exception as e:
                st.error(f"发送失败 / Send failed: {str(e)}")

    # Action buttons at the bottom
    st.markdown("---")
    col1, col2 = st.columns(2)

    with col1:
        if st.button("🔄 新对话 / New Conversation", use_container_width=True):
            reset_current_conversation()
            # Keep current patient for new conversation
            if patient_info:
                st.session_state.selected_patient = patient_info
            st.rerun()

    with col2:
        if st.button("📊 结束问诊 / End Consultation", use_container_width=True):
            try:
                client = st.session_state.backend_client
                client.end_conversation(st.session_state.current_conversation_id)
                st.success("✅ 问诊已结束 / Consultation ended")
                st.rerun()
            except Exception as e:
                st.error(f"结束失败 / End failed: {str(e)}")
