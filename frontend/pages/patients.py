# Patient Management Page

import sys
from pathlib import Path
from typing import Any

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.utils.helpers import (
    patient_create_form,
    display_patient_info,
    format_timestamp,
)


def patient_management_page():
    """Patient management page"""
    st.title("👥 患者管理 / Patient Management")
    st.markdown("---")

    client = st.session_state.backend_client

    # Action buttons row
    col1, col2, col3 = st.columns(3)

    with col1:
        if st.button("➕ 新建患者 / Create Patient", type="primary", use_container_width=True):
            st.session_state.show_create_form = True
            st.rerun()

    with col2:
        if st.button("🔄 刷新列表 / Refresh", use_container_width=True):
            st.rerun()

    with col3:
        if st.button("💬 开始对话 / Start Chat", use_container_width=True):
            # Switch to chat page
            st.session_state.current_page = "chat"
            st.rerun()

    st.markdown("---")

    # Show create form if triggered
    if st.session_state.get('show_create_form'):
        st.markdown("### 📝 新建患者 / Create New Patient")
        new_patient = patient_create_form()
        if new_patient:
            try:
                created = client.create_patient(new_patient)
                st.success(f"✅ 患者已创建 / Patient created: {created['name']}")
                st.session_state.show_create_form = False
                st.rerun()
            except Exception as e:
                st.error(f"创建失败 / Creation failed: {str(e)}")
        if st.button("取消 / Cancel"):
            st.session_state.show_create_form = False
            st.rerun()
        return

    # Search and filter
    col1, col2 = st.columns(2)

    with col1:
        search_query = st.text_input(
            "🔍 搜索患者 / Search Patients",
            placeholder="输入患者姓名搜索 / Enter patient name to search",
            label_visibility="collapsed"
        )

    with col2:
        limit = st.selectbox(
            "每页显示 / Per Page",
            options=[10, 25, 50, 100],
            index=1,
            label_visibility="collapsed"
        )

    # Load patients
    try:
        patients = client.list_patients(
            search=search_query if search_query else None,
            limit=limit
        )

        # Display metrics
        st.markdown("---")
        m1, m2, m3 = st.columns(3)
        with m1:
            st.metric("总患者数 / Total Patients", len(patients))
        with m2:
            # Count active patients (with recent conversations)
            active_count = sum(1 for p in patients if p.get('updated_at'))
            st.metric("活跃患者 / Active Patients", active_count)
        with m3:
            st.metric("当前页 / Current Page", f"{len(patients)} / {limit}")

        st.markdown("---")

        if not patients:
            st.info("📭 暂无患者记录 / No patient records found")

            if search_query:
                if st.button("清除搜索 / Clear Search"):
                    st.rerun()
            else:
                st.markdown("""
                ### 💡 提示 / Tips

                点击 **"新建患者 / Create Patient"** 按钮创建第一个患者记录。

                ---
                Click the **"Create Patient"** button to create the first patient record.
                """)
        else:
            # Display patient list
            st.markdown("### 📋 患者列表 / Patient List")

            for patient in patients:
                with st.container():
                    # Patient card header
                    col1, col2, col3, col4 = st.columns([3, 2, 2, 3])

                    with col1:
                        st.markdown(f"#### 👤 {patient.get('name', 'N/A')}")

                    with col2:
                        st.caption(f"🆔 {patient.get('patient_id', '')[:8]}...")

                    with col3:
                        # Gender display
                        gender_map = {"male": "男 / Male", "female": "女 / Female", "other": "其他 / Other"}
                        gender = gender_map.get(patient.get('gender'), patient.get('gender', 'N/A'))
                        st.caption(f"⚧️ {gender}")

                    with col4:
                        # Action buttons
                        btn_col1, btn_col2, btn_col3, btn_col4, btn_col5 = st.columns(5)

                        with btn_col1:
                            if st.button(
                                "➕",
                                key=f"new_chat_{patient['patient_id']}",
                                help="新对话 / New Chat",
                                use_container_width=True
                            ):
                                st.session_state.selected_patient = patient
                                st.session_state.current_page = "chat"
                                st.rerun()

                        with btn_col2:
                            if st.button(
                                "📊",
                                key=f"long_term_{patient['patient_id']}",
                                help="长期管理 / Long-term Management",
                                use_container_width=True
                            ):
                                st.session_state.selected_patient = patient
                                st.session_state.current_page = "long_term"
                                st.rerun()

                        with btn_col3:
                            if st.button(
                                "👁️",
                                key=f"view_{patient['patient_id']}",
                                help="查看详情 / View Details",
                                use_container_width=True
                            ):
                                st.session_state.viewing_patient = patient
                                st.rerun()

                        with btn_col4:
                            if st.button(
                                "✏️",
                                key=f"edit_{patient['patient_id']}",
                                help="编辑 / Edit",
                                use_container_width=True
                            ):
                                st.session_state.editing_patient = patient
                                st.rerun()

                        with btn_col5:
                            if st.button(
                                "🗑️",
                                key=f"delete_{patient['patient_id']}",
                                help="删除 / Delete",
                                use_container_width=True
                            ):
                                # Confirm deletion
                                if st.session_state.get(f'confirm_delete_patient_{patient["patient_id"]}', False):
                                    try:
                                        client.delete_patient(patient['patient_id'])
                                        st.success(f"✅ 患者已删除 / Patient deleted: {patient.get('name')}")
                                        st.session_state.pop(f'confirm_delete_patient_{patient["patient_id"]}', None)
                                        # Clear viewing/editing states if this patient
                                        if st.session_state.get('viewing_patient', {}).get('patient_id') == patient['patient_id']:
                                            st.session_state.viewing_patient = None
                                        if st.session_state.get('editing_patient', {}).get('patient_id') == patient['patient_id']:
                                            st.session_state.editing_patient = None
                                        st.rerun()
                                    except Exception as e:
                                        st.error(f"删除失败 / Delete failed: {str(e)}")
                                        st.session_state.pop(f'confirm_delete_patient_{patient["patient_id"]}', None)
                                else:
                                    st.session_state[f'confirm_delete_patient_{patient["patient_id"]}'] = True
                                    st.rerun()

                    # Show deletion confirmation warning if pending
                    if st.session_state.get(f'confirm_delete_patient_{patient["patient_id"]}', False):
                        st.warning(f"⚠️ 确认删除患者 {patient.get('name')}？再次点击删除按钮确认。/ Confirm delete patient {patient.get('name')}? Click delete button again to confirm.")

                    # Show recent conversations below each patient
                    try:
                        patient_convs = client.get_patient_conversations(patient['patient_id'], limit=5)
                        if patient_convs:
                            with st.expander(f"💬 最近对话 ({len(patient_convs)}) / Recent Conversations"):
                                for conv in patient_convs:
                                    conv_id = conv.get('conversation_id')
                                    status_emoji = {
                                        "active": "💬",
                                        "completed": "✅",
                                        "abandoned": "⏹️"
                                    }.get(conv.get('status'), "💭")

                                    c1, c2 = st.columns([3, 1])

                                    with c1:
                                        st.caption(
                                            f"{status_emoji} {conv.get('target', 'N/A')} - "
                                            f"{format_timestamp(conv.get('created_at', ''))}"
                                        )

                                    with c2:
                                        if st.button(
                                            "继续",
                                            key=f"list_continue_{conv_id}",
                                            use_container_width=True
                                        ):
                                            # Load conversation and switch to chat
                                            try:
                                                from frontend.utils.helpers import load_conversation
                                                messages = client.get_conversation_messages(conv_id)

                                                display_messages = [
                                                    {
                                                        "role": msg["role"],
                                                        "content": msg["content"],
                                                        "timestamp": msg["timestamp"]
                                                    }
                                                    for msg in messages
                                                ]

                                                load_conversation(conv_id, display_messages, patient)
                                                st.session_state.selected_patient_for_conversations = patient
                                                st.session_state.current_page = "chat"
                                                st.rerun()
                                            except Exception as e:
                                                st.error(f"加载失败: {str(e)}")
                    except:
                        pass  # Skip if conversations fail to load

                    st.markdown("---")

    except Exception as e:
        st.error(f"加载患者列表失败 / Failed to load patients: {str(e)}")

    # Patient detail modal (using expander)
    if st.session_state.get('viewing_patient'):
        patient = st.session_state.viewing_patient
        st.markdown("---")
        st.markdown("### 👁️ 患者详情 / Patient Details")

        display_patient_info(patient)

        # Show additional info
        col1, col2 = st.columns(2)

        with col1:
            st.markdown("**📅 注册时间 / Created**")
            st.caption(format_timestamp(patient.get('created_at', '')))

        with col2:
            st.markdown("**🔄 更新时间 / Updated**")
            st.caption(format_timestamp(patient.get('updated_at', '')))

        # Show conversations with continue buttons
        try:
            conversations = client.get_patient_conversations(patient['patient_id'], limit=100)
            st.markdown(f"**💬 历史对话 / Conversations**: {len(conversations)}")

            if conversations:
                # Sort conversations by created_at (newest first)
                from datetime import datetime
                conversations_sorted = sorted(
                    conversations,
                    key=lambda x: x.get('created_at', ''),
                    reverse=True
                )

                with st.expander("查看历史对话 / View Conversation History", expanded=True):
                    for conv in conversations_sorted[:10]:  # Show last 10
                        conv_id = conv.get('conversation_id')
                        status_emoji = {
                            "active": "💬",
                            "completed": "✅",
                            "abandoned": "⏹️"
                        }.get(conv.get('status'), "💭")

                        col1, col2, col3 = st.columns([3, 2, 2])

                        with col1:
                            st.markdown(
                                f"{status_emoji} **{conv.get('target', 'N/A')}**"
                            )
                            st.caption(f"{format_timestamp(conv.get('created_at', ''))}")

                        with col2:
                            st.caption(f"{conv.get('message_count', 0)} 条消息 / msgs")

                        with col3:
                            if st.button(
                                "继续 / Continue",
                                key=f"pm_continue_{conv_id}",
                                type="primary",
                                use_container_width=True
                            ):
                                # Load conversation and switch to chat page
                                try:
                                    from frontend.utils.helpers import load_conversation
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

                                    # Set up session state for chat
                                    load_conversation(conv_id, display_messages, patient)
                                    st.session_state.selected_patient_for_conversations = patient
                                    st.session_state.viewing_patient = None
                                    st.session_state.current_page = "chat"
                                    st.rerun()
                                except Exception as e:
                                    st.error(f"加载对话失败 / Failed to load: {str(e)}")

                if len(conversations) > 10:
                    st.caption(f"... 还有 {len(conversations) - 10} 条对话 / and {len(conversations) - 10} more")

        except Exception as e:
            st.warning(f"无法加载对话历史 / Failed to load conversations: {str(e)}")

        # Action buttons
        btn_col1, btn_col2, btn_col3, btn_col4 = st.columns(4)

        with btn_col1:
            if st.button("💬 开始对话 / Start Chat", type="primary", use_container_width=True):
                st.session_state.selected_patient = patient
                st.session_state.viewing_patient = None
                st.session_state.current_page = "chat"
                st.rerun()

        with btn_col2:
            if st.button("✏️ 编辑 / Edit", use_container_width=True):
                st.session_state.editing_patient = patient
                st.session_state.viewing_patient = None
                st.rerun()

        with btn_col3:
            # Delete button with confirmation
            delete_key = f'detail_delete_{patient["patient_id"]}'
            if st.button(
                "🗑️ 删除 / Delete",
                key=delete_key,
                use_container_width=True
            ):
                if st.session_state.get(f'confirm_delete_patient_{patient["patient_id"]}', False):
                    try:
                        client.delete_patient(patient['patient_id'])
                        st.success(f"✅ 患者已删除 / Patient deleted: {patient.get('name')}")
                        st.session_state.pop(f'confirm_delete_patient_{patient["patient_id"]}', None)
                        st.session_state.viewing_patient = None
                        st.rerun()
                    except Exception as e:
                        st.error(f"删除失败 / Delete failed: {str(e)}")
                        st.session_state.pop(f'confirm_delete_patient_{patient["patient_id"]}', None)
                else:
                    st.session_state[f'confirm_delete_patient_{patient["patient_id"]}'] = True
                    st.rerun()

        with btn_col4:
            if st.button("✕ 关闭 / Close", use_container_width=True):
                st.session_state.viewing_patient = None
                # Cancel deletion confirmation if pending
                if f'confirm_delete_patient_{patient["patient_id"]}' in st.session_state:
                    st.session_state.pop(f'confirm_delete_patient_{patient["patient_id"]}', None)
                st.rerun()

        # Show deletion confirmation warning
        if st.session_state.get(f'confirm_delete_patient_{patient["patient_id"]}', False):
            st.error(f"⚠️ 确认删除患者？所有对话记录将被永久删除！/ Confirm delete patient? All conversation history will be permanently deleted!")
            st.caption("请再次点击删除按钮确认 / Click delete button again to confirm")

    # Patient edit modal
    if st.session_state.get('editing_patient'):
        patient = st.session_state.editing_patient
        st.markdown("---")
        st.markdown("### ✏️ 编辑患者 / Edit Patient")

        with st.form("edit_patient_form"):
            col1, col2 = st.columns(2)

            with col1:
                name = st.text_input("姓名 / Name*", value=patient.get('name', ''), key="edit_name")
                age = st.number_input(
                    "年龄 / Age*",
                    min_value=0,
                    max_value=150,
                    value=patient.get('age', 30),
                    key="edit_age"
                )
                gender = st.selectbox(
                    "性别 / Gender*",
                    ["男 / Male", "女 / Female", "其他 / Other"],
                    index=["男 / Male", "女 / Female", "其他 / Other"].index(
                        {"male": "男 / Male", "female": "女 / Female", "other": "其他 / Other"}.get(
                            patient.get('gender'), "男 / Male"
                        )
                    ),
                    key="edit_gender"
                )

            with col2:
                phone = st.text_input(
                    "电话 / Phone",
                    value=patient.get('phone', ''),
                    key="edit_phone"
                )
                address = st.text_input(
                    "地址 / Address",
                    value=patient.get('address', ''),
                    key="edit_address"
                )

            col_submit, col_cancel = st.columns(2)

            with col_submit:
                submit = st.form_submit_button("保存 / Save", type="primary", use_container_width=True)

            with col_cancel:
                cancel = st.form_submit_button("取消 / Cancel", use_container_width=True)

            if submit and name:
                gender_map = {"男 / Male": "male", "女 / Female": "female", "其他 / Other": "other"}
                update_data = {
                    "name": name,
                    "age": age,
                    "gender": gender_map[gender],
                    "phone": phone or None,
                    "address": address or None
                }

                try:
                    updated = client.update_patient(patient['patient_id'], update_data)
                    st.success(f"✅ 患者已更新 / Patient updated: {updated['name']}")
                    st.session_state.editing_patient = None
                    st.rerun()
                except Exception as e:
                    st.error(f"更新失败 / Update failed: {str(e)}")

            if cancel:
                st.session_state.editing_patient = None
                st.rerun()


def patients_page():
    """Main entry point for patients page"""
    patient_management_page()
