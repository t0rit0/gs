# Chat Page - Main consultation interface

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


def chat_page():
    """Main chat/consultation page"""
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
                    # This would call the actual DrHyper API
                    # For now, we'll simulate it
                    st.session_state.conversation_id = "demo-conversation-id"
                    st.session_state.current_patient_id = patient_info.get('patient_id', 'new-patient')

                    # Add welcome message
                    welcome_msg = f"您好，{patient_info['name']}。我是您的医疗助手。请问今天有什么可以帮助您的？"
                    st.session_state.messages.append({
                        "role": "ai",
                        "content": welcome_msg
                    })

                    st.success("✅ 问诊会话已初始化 / Consultation initialized")
                    st.rerun()

                except Exception as e:
                    st.error(f"初始化失败 / Initialization failed: {str(e)}")

        # Show demo mode notice
        st.markdown("---")
        st.warning("⚠️ **演示模式 / Demo Mode**: 当前使用模拟数据。实际使用时需要配置 DrHyper API。")
        st.markdown("""
        **配置说明 / Configuration:**

        1. 设置环境变量 `DRHYPER_API_KEY` 和 `DRHYPER_API_BASE`
        2. 或在系统设置页面配置 API 密钥

        Set environment variables `DRHYPER_API_KEY` and `DRHYPER_API_BASE`,
        or configure API key in Settings page.
        """)

    else:
        # Active conversation
        # Display patient info
        display_patient_info(st.session_state.patient_info)

        # Chat interface
        st.markdown("### 对话记录 / Conversation History")

        # Display message history
        for msg in st.session_state.messages:
            display_message(msg["role"], msg["content"])

        # Chat input
        st.markdown("---")

        # Image upload section
        with st.expander("📷 上传医学影像 / Upload Medical Image"):
            uploaded_file = st.file_uploader(
                "选择影像文件 / Select image file",
                type=SUPPORTED_IMAGE_TYPES,
                help=f"支持格式: {', '.join(SUPPORTED_IMAGE_TYPES)} (最大 {MAX_IMAGE_SIZE_MB}MB)"
            )

            if uploaded_file:
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.image(uploaded_file, caption="预览 / Preview", use_container_width=True)
                with col2:
                    st.write("**文件信息 / File Info**")
                    st.text(f"名称: {uploaded_file.name}")
                    st.text(f"大小: {uploaded_file.size / 1024:.1f} KB")
                    st.text(f"类型: {uploaded_file.type}")

                    if st.button("📤 上传并分析 / Upload & Analyze", type="primary"):
                        with st.spinner("正在上传并分析影像 / Uploading and analyzing image..."):
                            # Demo: simulate image upload and analysis
                            st.success("✅ 影像已上传，AI 正在分析...")
                            st.info("🔍 **分析结果 / Analysis Result**: (模拟)")
                            st.json({
                                "findings": ["未见明显异常 / No obvious abnormalities"],
                                "confidence": 0.95,
                                "recommendation": "建议结合临床症状进一步评估 / Recommend further evaluation based on clinical symptoms"
                            })

        # Message input
        st.markdown("### 输入消息 / Input Message")

        with st.form("chat_form", clear_on_submit=True):
            col1, col2 = st.columns([5, 1])
            with col1:
                user_input = st.text_area(
                    "",
                    placeholder="请输入您的症状、问题或回复... / Enter your symptoms, questions, or responses...",
                    height=100,
                    label_visibility="collapsed"
                )
            with col2:
                st.write("")
                st.write("")
                submit = st.form_submit_button("发送 / Send", type="primary", use_container_width=True)

        # Handle message submission
        if submit and user_input:
            # Add user message
            st.session_state.messages.append({
                "role": "human",
                "content": user_input
            })

            # Get AI response (demo)
            with st.spinner("AI 正在思考... / AI is thinking..."):
                # Demo response - in production, this would call DrHyper API
                ai_response = generate_demo_response(user_input)

                st.session_state.messages.append({
                    "role": "ai",
                    "content": ai_response
                })

                st.rerun()

        # Action buttons
        col1, col2, col3 = st.columns(3)

        with col1:
            if st.button("🔄 新对话 / New Consultation"):
                reset_conversation()
                st.rerun()

        with col2:
            if st.button("💾 保存记录 / Save Record"):
                st.success("✅ 对话记录已保存 / Conversation saved")

        with col3:
            if st.button("📊 生成报告 / Generate Report"):
                st.info("📋 生成诊断报告功能 / Generate diagnostic report (即将推出 / Coming soon)")


def generate_demo_response(user_input: str) -> str:
    """
    Generate demo AI response (placeholder for actual DrHyper API)

    Args:
        user_input: User's message

    Returns:
        AI response
    """
    # Demo responses for common inputs
    demo_responses = {
        "头痛": "请问您的头痛是持续性的还是间歇性的？疼痛部位在头的一侧还是整个头部？是否伴有恶心、呕吐或视力模糊？",
        "头晕": "请问您的头晕是旋转感（天旋地转）还是头重脚轻的感觉？是否在改变体位时加重？是否有耳鸣或听力下降？",
        "咳嗽": "请问您的咳嗽是干咳还是有痰？痰是什么颜色的？是否伴有发热、胸痛或呼吸困难？咳嗽持续多久了？",
        "发热": "请问您测量的体温是多少？发热持续多久了？是否伴有寒战、出汗或其他症状？",
        "default": "感谢您提供的信息。为了更好地了解您的情况，我需要了解更多细节。请问您的症状持续多久了？是否有过类似的症状？是否有既往病史或正在服用的药物？"
    }

    # Simple keyword matching
    for keyword, response in demo_responses.items():
        if keyword in user_input:
            return response

    return demo_responses["default"]
