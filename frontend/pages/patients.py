# Patient Management Page

import streamlit as st


def patients_page():
    """Patient management page"""
    st.title("👥 患者管理 / Patient Management")
    st.markdown("---")

    st.info("🚧 此页面正在开发中 / This page is under development")

    # Placeholder content
    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("总患者数 / Total Patients", "0")

    with col2:
        st.metric("活跃会话 / Active Sessions", "0")

    with col3:
        st.metric("今天问诊 / Today's Consultations", "0")

    st.markdown("---")
    st.subheader("患者列表 / Patient List")
    st.write("暂无患者记录 / No patient records yet")
