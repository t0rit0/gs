# Main Streamlit Application

import sys
from pathlib import Path

import streamlit as st
from streamlit_option_menu import option_menu

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.config import PAGE_ICON, PAGE_LAYOUT, PAGE_TITLE
from frontend.utils.helpers import initialize_session_state


def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout=PAGE_LAYOUT,
        page_icon=PAGE_ICON,
        initial_sidebar_state="collapsed"  # Changed to collapsed for better UX
    )


def top_navigation():
    """Create top navigation bar for page switching"""
    # Use st.columns to create a top navigation bar
    col1, col2, col3, col4, col5, col6 = st.columns([1, 2, 2, 2, 2, 1])

    with col1:
        st.markdown(f"### {PAGE_ICON}")

    with col2:
        if st.button(
            "💬 对话问诊 / Consultation",
            use_container_width=True,
            type="primary" if st.session_state.get('current_page') == 'chat' else "secondary"
        ):
            st.session_state.current_page = 'chat'
            st.rerun()

    with col3:
        if st.button(
            "👥 患者管理 / Patients",
            use_container_width=True,
            type="primary" if st.session_state.get('current_page') == 'patients' else "secondary"
        ):
            st.session_state.current_page = 'patients'
            st.rerun()

    with col4:
        # Long-term management (only enabled if patient selected)
        patient = st.session_state.get('selected_patient') or st.session_state.get('viewing_patient')
        disabled = patient is None
        
        if st.button(
            "📊 长期管理 / Long-term",
            use_container_width=True,
            type="primary" if st.session_state.get('current_page') == 'long_term' else "secondary",
            disabled=disabled
        ):
            st.session_state.current_page = 'long_term'
            st.rerun()
        
        if disabled:
            st.caption("💡 请先选择患者 / Select patient first")

    with col5:
        if st.button(
            "⚙️ 系统设置 / Settings",
            use_container_width=True,
            type="primary" if st.session_state.get('current_page') == 'settings' else "secondary"
        ):
            st.session_state.current_page = 'settings'
            st.rerun()

    with col6:
        # Backend status indicator
        try:
            from frontend.utils.backend_client import BackendClient
            client = BackendClient()
            health = client.health_check()
            st.markdown(f'<div style="text-align: center; color: green;">●</div>', unsafe_allow_html=True)
            st.caption("在线 / Online")
        except:
            st.markdown(f'<div style="text-align: center; color: red;">●</div>', unsafe_allow_html=True)
            st.caption("离线 / Offline")

    st.markdown("---")


def sidebar():
    """Create sidebar with additional information"""
    with st.sidebar:
        st.title(f"{PAGE_ICON} {PAGE_TITLE}")
        st.markdown("---")

        # System status
        st.markdown("### 系统状态 / System Status")

        try:
            from frontend.utils.backend_client import BackendClient
            client = BackendClient()
            health = client.health_check()
            st.success(f"✅ 后端服务正常 / Backend OK")
            st.caption(f"版本 / Version: {health.get('version', 'N/A')}")
        except Exception as e:
            st.error(f"❌ 后端连接失败 / Backend Error")
            st.caption(f"{str(e)[:50]}...")

        st.markdown("---")

        # Current session info
        if st.session_state.get('current_conversation_id'):
            st.markdown("### 当前会话 / Current Session")

            if st.session_state.get('current_patient_info'):
                patient = st.session_state.current_patient_info
                st.info(f"**{patient.get('name', 'N/A')}**\n{patient.get('age', 'N/A')}岁, {patient.get('gender', 'N/A')}")

            st.caption(f"会话 ID / Session ID:\n`{st.session_state.current_conversation_id[:8]}...`")
            st.caption(f"消息数 / Messages: {len(st.session_state.get('messages', []))}")

        st.markdown("---")

        # Quick actions
        st.markdown("### 快捷操作 / Quick Actions")

        if st.button("🔄 重置会话 / Reset Session", use_container_width=True):
            from frontend.utils.helpers import reset_current_conversation
            reset_current_conversation()
            st.rerun()

        if st.button("🏠 返回首页 / Home", use_container_width=True):
            st.session_state.current_page = 'chat'
            st.rerun()

        st.markdown("---")
        st.caption("基于 DrHyper 诊断引擎\nPowered by DrHyper Diagnostic Engine")


def main():
    """Main application entry point"""
    setup_page_config()
    initialize_session_state()

    # Custom CSS for better styling
    st.markdown("""
        <style>
        .stApp {
            max-width: 1400px;
            margin: 0 auto;
        }
        .main-header {
            padding: 1rem 0;
            border-bottom: 2px solid #f0f0f0;
            margin-bottom: 2rem;
        }
        /* Hide default sidebar */
        [data-testid="stSidebar"] {
            display: none;
        }
        /* Show our custom sidebar */
        [data-testid="stSidebar"][aria-expanded="true"] {
            display: block;
        }
        </style>
    """, unsafe_allow_html=True)

    # Top navigation bar
    top_navigation()

    # Sidebar (can be toggled)
    # We use a custom approach for sidebar since we want it visible
    # Streamlit's sidebar is always there, we just use it
    # The custom CSS hides it by default but it can be shown

    # Route to appropriate page
    page = st.session_state.get('current_page', 'chat')

    if page == "chat":
        from frontend.pages.chat import chat_page
        chat_page()
    elif page == "patients":
        from frontend.pages.patients import patients_page
        patients_page()
    elif page == "long_term":
        from frontend.pages.long_term_management import long_term_management_page
        # Get patient info
        patient = st.session_state.get('selected_patient') or st.session_state.get('viewing_patient')
        if patient:
            from frontend.utils.backend_client import BackendClient
            client = BackendClient()
            api_base_url = client.base_url
            long_term_management_page(
                patient_id=patient['patient_id'],
                patient_name=patient['name'],
                api_base_url=api_base_url
            )
        else:
            st.error("请先选择患者 / Please select a patient first")
            st.session_state.current_page = "patients"
            st.rerun()
    elif page == "settings":
        from frontend.pages.settings import settings_page
        settings_page()


if __name__ == "__main__":
    main()
