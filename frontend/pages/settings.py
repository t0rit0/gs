# Settings Page

import streamlit as st
import os


def settings_page():
    """Settings page"""
    st.title("⚙️ 系统设置 / System Settings")
    st.markdown("---")

    st.info("🚧 此页面正在开发中 / This page is under development")

    # API Configuration
    st.subheader("API 配置 / API Configuration")

    col1, col2 = st.columns(2)

    with col1:
        api_base = st.text_input(
            "API Base URL",
            value=os.getenv("DRHYPER_API_BASE", "http://localhost:8000"),
            help="DrHyper API 服务器地址"
        )

    with col2:
        api_key = st.text_input(
            "API Key",
            value=os.getenv("DRHYPER_API_KEY", ""),
            type="password",
            help="DrHyper API 密钥（如果需要）"
        )

    if st.button("保存配置 / Save Settings"):
        st.success("✅ 配置已保存 / Settings saved")
        st.info("请重启应用以应用更改 / Please restart the app to apply changes")

    st.markdown("---")

    # System info
    st.subheader("系统信息 / System Information")
    st.json({
        "frontend_version": "1.0.0",
        "api_base": api_base,
        "api_configured": bool(api_key)
    })
