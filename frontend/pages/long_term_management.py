"""
Long-term Patient Management Page

Week 7 - Health Metrics Management
"""
import sys
from pathlib import Path
from datetime import datetime, timedelta

import streamlit as st

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from frontend.components.metrics import (
    render_metric_entry_form,
    render_metrics_timeline,
    render_metric_trend,
    METRIC_CONFIGS
)


def long_term_management_page(patient_id: str, patient_name: str, api_base_url: str):
    """
    Long-term patient management page

    Features:
    - Health metrics entry
    - Metrics timeline visualization
    - Trend analysis
    """
    # Note: Do NOT clear selected_patient/viewing_patient as they are needed
    # to maintain patient context across page reruns (e.g., when selecting metrics)

    st.title(f"📊 长期健康管理 / Long-term Management")
    st.markdown(f"**患者 / Patient**: {patient_name} (ID: {patient_id})")
    st.markdown("---")
    
    # Sidebar navigation
    st.sidebar.title("📋 功能菜单 / Menu")
    menu_options = [
        "📊 指标总览 / Metrics Overview",
        "📝 录入数据 / Record Data",
        "📥 批量导入 / Bulk Import",
    ]
    selected = st.sidebar.radio("选择功能 / Select Feature", menu_options)
    
    if selected == "📊 指标总览 / Metrics Overview":
        render_metrics_overview_section(patient_id, api_base_url)
    
    elif selected == "📝 录入数据 / Record Data":
        st.markdown("### 📝 手动录入健康指标 / Manual Entry")
        render_metric_entry_form(
            patient_id=patient_id,
            api_base_url=api_base_url,
            on_success=lambda data: st.success(f"✅ 记录已保存！Record saved!")
        )
    
    elif selected == "📥 批量导入 / Bulk Import":
        render_bulk_import_form(patient_id, api_base_url)


def render_metrics_overview_section(patient_id: str, api_base_url: str):
    """Render metrics overview section with charts and tables per metric type"""
    st.markdown("### 📊 指标概览 / Metrics Overview")
    
    # Time range selection - Number input
    time_range_col1, time_range_col2 = st.columns([3, 1])
    with time_range_col1:
        selected_days = st.number_input(
            "时间范围 / Time Range (天 / days)",
            min_value=1,
            max_value=365,
            value=30,
            step=1,
            key="overview_time_range"
        )

    # Metric type filter
    metric_filter = st.selectbox(
        "📊 选择指标类型 / Select Metric Type",
        options=["All"] + list(METRIC_CONFIGS.keys()),
        format_func=lambda x: "全部 / All" if x == "All" else f"{METRIC_CONFIGS.get(x, {}).get('icon', '📊')} {x}",
        key="metric_type_filter"
    )

    # Fetch all metrics
    try:
        import requests
        import pandas as pd

        response = requests.get(f"{api_base_url}/api/patients/{patient_id}/metrics", params={"limit": 500})

        if response.status_code == 200:
            records = response.json()

            if records:
                # Filter by selected time range
                cutoff_date = datetime.now() - timedelta(days=selected_days)

                filtered_records = []
                for record in records:
                    try:
                        record_date = datetime.fromisoformat(record["measured_at"].replace("Z", "+00:00"))
                        if record_date >= cutoff_date:
                            filtered_records.append(record)
                    except:
                        filtered_records.append(record)

                # Group by metric name
                metrics_by_type = {}
                for record in filtered_records:
                    metric_name = record["metric_name"]
                    if metric_name not in metrics_by_type:
                        metrics_by_type[metric_name] = []
                    metrics_by_type[metric_name].append(record)

                # Display chart and table for each metric type (filtered)
                for metric_name, metric_records in sorted(metrics_by_type.items()):
                    # Apply metric filter
                    if metric_filter != "All" and metric_name != metric_filter:
                        continue
                    
                    icon = METRIC_CONFIGS.get(metric_name, {}).get("icon", "📊")
                    st.markdown(f"---")
                    st.markdown(f"#### {icon} {metric_name}")
                    
                    # Sort by date
                    metric_records.sort(key=lambda x: x["measured_at"])
                    
                    # Prepare data for chart
                    dates = []
                    values = []
                    component_names = []  # Track component names for legend
                    
                    for record in metric_records:
                        dates.append(datetime.fromisoformat(record["measured_at"].replace("Z", "+00:00")))
                        
                        # Check if API returned component data
                        component_1 = record.get("component_1")
                        component_2 = record.get("component_2")
                        
                        if component_1 and component_2 and isinstance(component_1, dict) and isinstance(component_2, dict):
                            # Use component values from API with dynamic names
                            comp1_name = component_1.get("name", "Component 1")
                            comp2_name = component_2.get("name", "Component 2")
                            
                            # Store component names for legend (use first record)
                            if not component_names:
                                component_names = [comp1_name, comp2_name]
                            
                            values.append({
                                comp1_name: component_1.get("value", 0),
                                comp2_name: component_2.get("value", 0)
                            })
                        else:
                            # Fallback: parse value_string or use value_numeric
                            value_str = record.get("value_string", "")
                            value_num = record.get("value_numeric")
                            
                            if value_str and "/" in value_str:
                                # Composite value (e.g., "145/92")
                                parts = value_str.split("/")
                                if not component_names:
                                    component_names = ["Component 1", "Component 2"]
                                values.append({
                                    component_names[0]: float(parts[0]),
                                    component_names[1]: float(parts[1])
                                })
                            elif value_num is not None:
                                # Single numeric value (e.g., Heart Rate)
                                if not component_names:
                                    component_names = ["Value"]
                                values.append({
                                    component_names[0]: float(value_num)
                                })
                            else:
                                # No value available
                                values.append({"value": 0})
                    
                    # Import chart functions and create chart
                    from frontend.components.metrics import create_line_chart, create_bp_chart
                    
                    if values and isinstance(values[0], dict):
                        # Check if it's a single-value metric or multi-component
                        first_value = values[0]
                        if len(first_value) == 1:
                            # Single value metric (e.g., Heart Rate, Glucose)
                            fig = create_line_chart(dates, [list(v.values())[0] for v in values], metric_name)
                        else:
                            # Multi-component metric (e.g., Blood Pressure)
                            fig = create_bp_chart(dates, values, metric_name, component_names)
                    else:
                        fig = create_line_chart(dates, [], metric_name)
                    
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Display table for this metric
                    st.markdown(f"##### 📋 记录详情 / Records Detail")

                    # Prepare table data with dynamic component names
                    table_data = []
                    for record in sorted(metric_records, key=lambda x: x["measured_at"], reverse=True):
                        row = {"日期 / Date": record["measured_at"][:16].replace("T", " ")}
                        
                        # Add component values dynamically
                        component_1 = record.get("component_1")
                        component_2 = record.get("component_2")
                        
                        if component_1 and isinstance(component_1, dict):
                            comp1_name = component_1.get("name", "Component 1")
                            row[f"{comp1_name}"] = component_1.get("value", "-")
                        
                        if component_2 and isinstance(component_2, dict):
                            comp2_name = component_2.get("name", "Component 2")
                            row[f"{comp2_name}"] = component_2.get("value", "-")
                        
                        # If no components, show value_string or value_numeric
                        if not component_1 and not component_2:
                            value = record.get("value_string") or record.get("value_numeric", "-")
                            row["数值 / Value"] = value
                        
                        row["单位 / Unit"] = record.get("unit", "-")
                        row["来源 / Source"] = record.get("source", "manual").replace("_", " ").title()
                        
                        table_data.append(row)

                    df = pd.DataFrame(table_data)
                    st.dataframe(df, use_container_width=True, hide_index=True)

                    # Summary stats
                    st.caption(f"共 {len(metric_records)} 条记录 (时间范围：{selected_days}天)")
            else:
                st.info("暂无记录 / No records yet")
        
    except Exception as e:
        st.error(f"加载失败 / Failed to load: {str(e)}")


def render_bulk_import_form(patient_id: str, api_base_url: str):
    """
    Render bulk import form for CSV/Excel upload
    
    Supports:
    - CSV file upload
    - Excel file upload (.xlsx)
    - Template download
    - Dynamic component columns (column name as component name)
    """
    st.markdown("### 📥 批量导入健康指标 / Bulk Import Health Metrics")
    
    st.markdown("""
    **支持的文件格式 / Supported Formats**: CSV, Excel (.xlsx)
    
    **数据格式要求 / Data Format Requirements**:
    - `metric_name`: 指标名称 (e.g., "Blood Pressure", "Heart Rate")
    - `value`: 数值 (e.g., "145/92" for BP, or "72" for heart rate)
    - `unit`: 单位 (e.g., "mmHg", "bpm", "mg/dL")
    - `measured_at`: 测量时间 (ISO format: "2026-03-13T10:00:00")
    - `source`: 来源 (optional: "manual", "wearable", "clinical_exam", "lab_result")
    - `context`: 上下文 (optional: "morning_reading", "fasting", etc.)
    - **其他列名将作为 component name** (e.g., "Systolic", "Diastolic", "Heart_Rate")
    
    **示例 / Example**:
    | metric_name | value | unit | measured_at | Systolic | Diastolic | source |
    |-------------|-------|------|-------------|----------|-----------|--------|
    | Blood Pressure | 145/92 | mmHg | 2026-03-13T10:00:00 | 145 | 92 | manual |
    | Heart Rate | 72 | bpm | 2026-03-13T10:00:00 | | | manual |
    """)
    
    # Download template button
    template_csv = """metric_name,value,unit,measured_at,Systolic,Diastolic,source,context
Blood Pressure,145/92,mmHg,2026-03-13T10:00:00,145,92,manual,morning_reading
Heart Rate,72,bpm,2026-03-13T10:00:00,,,manual,morning_reading
Blood Glucose,95,mg/dL,2026-03-13T08:00:00,,,manual,fasting
Weight,75.5,kg,2026-03-13T07:00:00,,,manual,morning_reading
"""
    
    st.download_button(
        label="📥 下载模板 / Download Template CSV",
        data=template_csv,
        file_name="health_metrics_template.csv",
        mime="text/csv",
        use_container_width=True
    )
    
    st.markdown("---")
    
    # File uploader
    uploaded_file = st.file_uploader(
        "上传 CSV 或 Excel 文件 / Upload CSV or Excel File",
        type=["csv", "xlsx"],
        help="支持 CSV 和 Excel 格式 / Supports CSV and Excel formats"
    )
    
    if uploaded_file:
        try:
            import pandas as pd
            
            # Read file
            if uploaded_file.name.endswith('.csv'):
                df = pd.read_csv(uploaded_file)
            else:
                df = pd.read_excel(uploaded_file)
            
            st.markdown("### 📊 数据预览 / Data Preview")
            st.dataframe(df.head(10), use_container_width=True)
            st.caption(f"共 {len(df)} 条记录 / Total {len(df)} records")
            
            # Validate data
            required_columns = ["metric_name", "value", "unit", "measured_at"]
            missing_columns = [col for col in required_columns if col not in df.columns]
            
            if missing_columns:
                st.error(f"❌ 缺少必需列 / Missing required columns: {missing_columns}")
                return
            
            # Detect component columns (any column not in standard fields)
            standard_columns = ["metric_name", "value", "unit", "measured_at", "source", "context"]
            component_columns = [col for col in df.columns if col not in standard_columns]
            
            if component_columns:
                st.info(f"🔍 检测到 Component 列 / Detected Component Columns: {', '.join(component_columns)}")
            
            # Confirm import
            st.markdown("### ✅ 确认导入 / Confirm Import")
            
            if st.button(f"📥 导入 {len(df)} 条记录 / Import {len(df)} Records", type="primary"):
                import requests
                
                success_count = 0
                error_count = 0
                errors = []
                
                progress_bar = st.progress(0)
                
                for idx, row in df.iterrows():
                    try:
                        payload = {
                            "metric_name": str(row["metric_name"]),
                            "value": row["value"],
                            "unit": str(row["unit"]),
                            "measured_at": str(row["measured_at"]),
                            "source": str(row.get("source", "manual")),
                            "context": str(row.get("context", "")) if pd.notna(row.get("context")) else None
                        }
                        
                        # Add dynamic component columns
                        for i, col in enumerate(component_columns):
                            if pd.notna(row.get(col)) and str(row.get(col)).strip():
                                payload[f"component_{i+1}_name"] = col
                                payload[f"component_{i+1}_value"] = float(row[col])
                        
                        # Remove None values
                        payload = {k: v for k, v in payload.items() if v is not None}
                        
                        response = requests.post(
                            f"{api_base_url}/api/patients/{patient_id}/metrics",
                            json=payload
                        )
                        
                        if response.status_code == 201:
                            success_count += 1
                        else:
                            error_count += 1
                            errors.append(f"Row {idx + 1}: {response.text}")
                    
                    except Exception as e:
                        error_count += 1
                        errors.append(f"Row {idx + 1}: {str(e)}")
                    
                    # Update progress
                    progress_bar.progress((idx + 1) / len(df))
                
                # Show results
                st.markdown("### 📊 导入结果 / Import Results")
                col1, col2 = st.columns(2)
                with col1:
                    st.success(f"✅ 成功导入 / Success: {success_count}")
                with col2:
                    if error_count > 0:
                        st.error(f"❌ 失败 / Failed: {error_count}")
                    else:
                        st.success("✅ 全部成功导入 / All records imported successfully!")
                
                if errors:
                    with st.expander(f"查看 {len(errors)} 个错误详情 / View Error Details"):
                        for error in errors[:10]:  # Show first 10 errors
                            st.error(error)
                        if len(errors) > 10:
                            st.caption(f"... 还有 {len(errors) - 10} 个错误 / ... and {len(errors) - 10} more errors")
                
                # Auto-refresh to show new data in overview
                if success_count > 0:
                    st.balloons()
                    st.info("🔄 数据已更新，请切换到'指标总览'查看 / Data updated, switch to 'Metrics Overview' to view")
        
        except Exception as e:
            st.error(f"❌ 文件处理失败 / File processing failed: {str(e)}")
