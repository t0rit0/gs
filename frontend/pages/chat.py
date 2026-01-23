# Chat Page - Split-pane interface with medical image analysis

import base64
import sys
from pathlib import Path

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.config import MAX_IMAGE_SIZE_MB, SUPPORTED_IMAGE_TYPES
from frontend.utils.drhyper_client import DrHyperClient
from frontend.utils.helpers import (
    display_message,
    display_patient_info,
    patient_info_form,
    reset_conversation,
)


def image_to_base64(image_file) -> str:
    """Convert uploaded image file to base64 string"""
    image_bytes = image_file.getvalue()
    base64_bytes = base64.b64encode(image_bytes)
    base64_string = base64_bytes.decode('utf-8')

    # Detect mime type
    mime_type = image_file.type
    return f"data:{mime_type};base64,{base64_string}"


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

        if st.session_state.image_analysis_report:
            # Display structured report
            report = st.session_state.image_analysis_report

            # Findings section - show key findings summary
            with st.expander("🔍 检查发现 / Findings", expanded=True):
                if isinstance(report, dict):
                    if "findings" in report:
                        findings = report["findings"]
                        if isinstance(findings, list):
                            for i, finding in enumerate(findings, 1):
                                st.markdown(f"**{i}.** {finding}")
                        else:
                            st.write(findings)

                    if "recommendation" in report:
                        st.info(f"💡 **建议 / Recommendation**: {report['recommendation']}")
                else:
                    st.write(report)

            # AI interpretation - show the full analysis report or AI response
            if isinstance(report, dict):
                if "full_report" in report:
                    # Show full report if available
                    with st.expander("🤖 AI 解读 / AI Interpretation", expanded=True):
                        st.write(report["full_report"])
                elif "findings" in report:
                    # Fallback: show findings as interpretation
                    findings = report["findings"]
                    if isinstance(findings, list) and len(findings) > 0:
                        with st.expander("🤖 AI 解读 / AI Interpretation", expanded=True):
                            for finding in findings:
                                st.write(f"• {finding}")
                else:
                    # Show last AI message from conversation as interpretation
                    if st.session_state.messages:
                        last_ai_msg = [m for m in reversed(st.session_state.messages) if m["role"] == "ai"]
                        if last_ai_msg:
                            with st.expander("🤖 AI 解读 / AI Interpretation", expanded=True):
                                st.write(last_ai_msg[0]["content"])
            elif isinstance(report, str):
                # If report is just a string, display it directly
                with st.expander("🤖 AI 解读 / AI Interpretation", expanded=True):
                    st.write(report)

            # Show raw JSON for debugging (outside the findings expander)
            if isinstance(report, dict):
                with st.expander("📄 原始数据 / Raw Data", expanded=False):
                    st.json(report)
        else:
            st.info("⏳ 等待 AI 分析结果... / Waiting for AI analysis...")


def display_thumbnail():
    """Display a clickable thumbnail to reopen the image panel"""
    if st.session_state.uploaded_image and st.session_state.thumbnail_visible:
        st.markdown("---")
        col1, col2 = st.columns([1, 5])

        with col1:
            # Create thumbnail
            st.image(
                st.session_state.uploaded_image,
                width=100,
                caption="点击查看 / Click to view"
            )

        with col2:
            st.write("")
            st.write("")
            if st.button("📷 打开医学影像 / Open Medical Image", key="reopen_image_panel"):
                st.session_state.image_panel_open = True
                st.session_state.thumbnail_visible = False
                st.rerun()


def chat_page():
    """Main chat/consultation page with split-pane layout"""

    st.title("💬 对话问诊 / Medical Consultation")
    st.markdown("---")

    # Initialize client
    if 'drhyper_client' not in st.session_state:
        st.session_state.drhyper_client = DrHyperClient()

    # Check if conversation is active
    if not st.session_state.conversation_id:
        # Show patient info form for new consultation
        st.info("👋 请填写患者信息以开始问诊 / Please fill in patient information to start consultation")

        patient_info = patient_info_form()

        if patient_info:
            # Store patient info and initialize conversation
            st.session_state.patient_info = patient_info

            with st.spinner("正在初始化问诊会话 / Initializing consultation..."):
                try:
                    client = st.session_state.drhyper_client

                    # Call the actual API
                    result = client.init_conversation(
                        patient_info={
                            "name": patient_info["name"],
                            "age": patient_info["age"],
                            "gender": patient_info["gender"]
                        }
                    )

                    st.session_state.conversation_id = result.get("conversation_id")
                    st.session_state.current_patient_id = patient_info.get('patient_id', 'new-patient')

                    # Add welcome message
                    welcome_msg = result.get("ai_message", f"您好，{patient_info['name']}。我是 Dr.Hyper，您的高血压专科AI助手。")
                    st.session_state.messages.append({
                        "role": "ai",
                        "content": welcome_msg
                    })

                    st.success("✅ 问诊会话已初始化 / Consultation initialized")
                    st.rerun()

                except Exception as e:
                    st.error(f"初始化失败 / Initialization failed: {str(e)}")
                    st.error("请检查后端服务是否正常运行，然后刷新页面重试。/ Please check if the backend service is running, then refresh the page to retry.")

    else:
        # Active conversation with split-pane layout
        if st.session_state.image_panel_open:
            # Split view: Image panel on left, Chat on right
            col_left, col_right = st.columns([1, 1])

            with col_left:
                display_image_panel()

            with col_right:
                display_chat_interface()
        else:
            # Full width chat view
            display_chat_interface()

        # Show thumbnail at the bottom when panel is closed
        display_thumbnail()


def display_chat_interface():
    """Display the chat interface"""
    # Display patient info
    display_patient_info(st.session_state.patient_info)

    # Chat messages
    st.markdown("### 💭 对话记录 / Conversation History")

    # Display message history
    for msg in st.session_state.messages:
        display_message(msg["role"], msg["content"])

    st.markdown("---")

    # Input section with image upload
    col1, col2 = st.columns([2, 1])

    # Text input and file upload in the same form
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

        # Show current image status
        if st.session_state.get('uploaded_image') and st.session_state.get('last_processed_image'):
            st.info("ℹ️ 图片已上传 / Image uploaded (上传新图片可重新分析 / Upload new to re-analyze)")

        # File uploader inside the form so it submits together with text
        uploaded_file = st.file_uploader(
            "医学影像上传 / Medical Image Upload",
            type=SUPPORTED_IMAGE_TYPES,
            help=f"支持: {', '.join(SUPPORTED_IMAGE_TYPES)} (最大 {MAX_IMAGE_SIZE_MB}MB)",
            label_visibility="collapsed",
            key="image_uploader"
        )

    # Handle form submission (text message + optional image)
    if submit:
        # Process image if uploaded and it's a NEW file
        base64_image = None
        image_attached = False

        if uploaded_file:
            # Check if this is a new file (not processed before)
            current_file_name = uploaded_file.name
            last_processed_file = st.session_state.get('last_processed_image', None)

            if current_file_name != last_processed_file:
                # This is a new image, process it
                image_attached = True

                # Store the uploaded image for display
                st.session_state.uploaded_image = uploaded_file

                # Convert to base64 for API
                base64_image = image_to_base64(uploaded_file)

                # Mark as processed
                st.session_state.last_processed_image = current_file_name
            else:
                # Same file as before, don't re-process
                # Just use the text message without image
                image_attached = False

        # Prepare message (text + optional image indicator)
        if user_input and image_attached:
            # Both text and NEW image
            message_content = f"{user_input} [已上传医学影像 / Medical image attached]"
        elif user_input:
            # Text only (or image was already processed)
            message_content = user_input
        elif image_attached:
            # Image only (NEW image without text)
            message_content = "请分析这张医学影像 / Please analyze this medical image"
        else:
            # Nothing to send
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
                client = st.session_state.drhyper_client

                # Call chat API with optional image
                images = [base64_image] if base64_image else None
                result = client.chat(
                    conversation_id=st.session_state.conversation_id,
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
                        st.session_state.image_analysis_report = analysis_report
                    else:
                        # Create fallback report if API didn't return one
                        st.session_state.image_analysis_report = {
                            "findings": ["影像已接收 / Image received", "AI 正在生成详细分析 / AI generating detailed analysis"],
                            "full_report": ai_response if ai_response else "影像分析已完成，但详细报告暂不可用。请查看对话历史中的 AI 回复。",
                            "recommendation": "请继续对话以获取更多分析信息 / Continue conversation for more analysis",
                            "image_count": 1
                        }
                    # Open the image panel
                    st.session_state.image_panel_open = True
                    st.session_state.thumbnail_visible = False

                if accomplish:
                    st.success("✅ 诊断完成 / Diagnosis Completed")

                st.rerun()

            except Exception as e:
                st.error(f"发送失败 / Send failed: {str(e)}")
                st.error("请检查后端服务是否正常运行。/ Please check if the backend service is running normally.")

    # Action buttons at the bottom
    st.markdown("---")
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("🔄 新对话 / New Consultation"):
            reset_conversation()
            st.rerun()

    with col2:
        if st.button("💾 保存记录 / Save Record"):
            try:
                client = st.session_state.drhyper_client
                client.save_conversation(st.session_state.conversation_id)
                st.success("✅ 对话记录已保存 / Conversation saved")
            except Exception as e:
                st.error(f"保存失败 / Save failed: {str(e)}")

    with col3:
        if st.button("📊 结束问诊 / End Consultation"):
            try:
                client = st.session_state.drhyper_client
                client.end_conversation(st.session_state.conversation_id)
                reset_conversation()
                st.success("✅ 问诊已结束 / Consultation ended")
                st.rerun()
            except Exception as e:
                st.error(f"结束失败 / End failed: {str(e)}")
