# Main Streamlit Application

import streamlit as st
from streamlit_option_menu import option_menu
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from frontend.config import (
    PAGE_TITLE, PAGE_LAYOUT, PAGE_ICON
)
from frontend.utils.helpers import initialize_session_state


def setup_page_config():
    """Configure Streamlit page settings"""
    st.set_page_config(
        page_title=PAGE_TITLE,
        layout=PAGE_LAYOUT,
        page_icon=PAGE_ICON,
        initial_sidebar_state="expanded"
    )


def sidebar_navigation():
    """Create sidebar navigation menu"""
    with st.sidebar:
        st.title(f"{PAGE_ICON} {PAGE_TITLE}")
        st.markdown("---")

        page = option_menu(
            menu_title="导航 / Navigation",
            options=[
                "对话问诊 / Consultation",
                "患者管理 / Patient Management",
                "系统设置 / Settings"
            ],
            icons=["chat-dots", "person-badge", "gear"],
            menu_icon="cast",
            default_index=0,
            styles={
                "container": {"padding": "5!important"},
                "icon": {"color": "orange", "font-size": "18px"},
                "nav-link": {
                    "font-size": "14px",
                    "text-align": "left",
                    "margin": "0px",
                }
            }
        )

        st.markdown("---")
        st.caption("基于 DrHyper 诊断引擎")
        st.caption("Powered by DrHyper Diagnostic Engine")

    return page


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
        </style>
    """, unsafe_allow_html=True)

    # Sidebar navigation
    page = sidebar_navigation()

    # Route to appropriate page
    if page == "对话问诊 / Consultation":
        from frontend.pages.chat import chat_page
        chat_page()
    elif page == "患者管理 / Patient Management":
        from frontend.pages.patients import patients_page
        patients_page()
    elif page == "系统设置 / Settings":
        from frontend.pages.settings import settings_page
        settings_page()


if __name__ == "__main__":
    main()
