"""
Health Metrics Components for Streamlit Frontend

Week 7 - Long-term Patient Management
"""
import streamlit as st
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Callable
import requests


# Metric configurations
METRIC_CONFIGS: Dict[str, Dict] = {
    "Blood Pressure": {
        "display_name": "Blood Pressure",
        "unit": "mmHg",
        "input_type": "composite",
        "component_1": "Systolic",
        "component_2": "Diastolic",
        "icon": "❤️",
        "category": "vital-signs"
    },
    "Heart Rate": {
        "display_name": "Heart Rate",
        "unit": "bpm",
        "input_type": "numeric",
        "min_value": 30,
        "max_value": 250,
        "icon": "💓",
        "category": "vital-signs"
    },
    "Blood Glucose": {
        "display_name": "Blood Glucose",
        "unit": "mg/dL",
        "input_type": "numeric",
        "min_value": 30,
        "max_value": 600,
        "icon": "🩸",
        "category": "laboratory"
    },
    "Weight": {
        "display_name": "Weight",
        "unit": "kg",
        "input_type": "numeric",
        "min_value": 20,
        "max_value": 300,
        "icon": "⚖️",
        "category": "vital-signs"
    },
    "Body Temperature": {
        "display_name": "Body Temperature",
        "unit": "°C",
        "input_type": "numeric",
        "min_value": 35.0,
        "max_value": 42.0,
        "icon": "🌡️",
        "category": "vital-signs"
    }
}


def render_metric_entry_form(
    patient_id: str,
    api_base_url: str,
    on_success: Optional[Callable] = None
):
    """
    Render metric entry form
    
    Args:
        patient_id: Current patient ID
        api_base_url: Backend API base URL
        on_success: Callback function after successful submission
    """
    st.subheader("📊 Record Health Metric")
    
    with st.form("metric_entry_form", clear_on_submit=True):
        col1, col2 = st.columns(2)
        
        with col1:
            metric_name = st.selectbox(
                "Metric Type",
                options=list(METRIC_CONFIGS.keys()),
                format_func=lambda x: f"{METRIC_CONFIGS[x]['icon']} {METRIC_CONFIGS[x]['display_name']}"
            )
        
        with col2:
            measured_at = st.date_input("Measurement Date", value=datetime.now())
        
        config = METRIC_CONFIGS[metric_name]
        
        st.markdown(f"### {config['icon']} {config['display_name']}")
        
        if config["input_type"] == "composite":
            col_comp1, col_comp2 = st.columns(2)
            
            with col_comp1:
                systolic = st.number_input(
                    config["component_1"],
                    min_value=50,
                    max_value=250,
                    value=120,
                    help=f"{config['component_1']} blood pressure"
                )
            
            with col_comp2:
                diastolic = st.number_input(
                    config["component_2"],
                    min_value=30,
                    max_value=150,
                    value=80,
                    help=f"{config['component_2']} blood pressure"
                )
            
            value = f"{systolic}/{diastolic}"
        else:
            value = st.number_input(
                f"Value ({config['unit']})",
                min_value=float(config.get("min_value", 0)),
                max_value=float(config.get("max_value", 1000)),
                value=float(config.get("placeholder", 0)),
                step=0.1 if "Temperature" in metric_name else 1.0
            )
        
        source = st.selectbox(
            "Source",
            options=["manual", "wearable", "clinical_exam", "lab_result"],
            format_func=lambda x: x.replace("_", " ").title()
        )
        
        submitted = st.form_submit_button("💾 Save Record", type="primary")
        
        if submitted:
            url = f"{api_base_url}/api/patients/{patient_id}/metrics"
            
            payload = {
                "metric_name": metric_name,
                "value": value,
                "unit": config["unit"],
                "measured_at": datetime.combine(measured_at, datetime.now().time()).isoformat(),
                "source": source,
                "metadata": {"entered_via": "streamlit_ui"}
            }
            
            try:
                response = requests.post(url, json=payload)
                response.raise_for_status()
                
                st.success(f"✅ {config['display_name']} recorded successfully!")
                
                if on_success:
                    on_success(response.json())
                
            except requests.exceptions.RequestException as e:
                st.error(f"❌ Failed to save: {str(e)}")


def render_metrics_timeline(
    patient_id: str,
    api_base_url: str,
    metric_names: Optional[List[str]] = None,
    days: int = 30
):
    """
    Render metrics timeline visualization
    
    Args:
        patient_id: Current patient ID
        api_base_url: Backend API base URL
        metric_names: List of metrics to display
        days: Number of days to show
    """
    st.subheader("📈 Health Metrics Timeline")
    
    # Metric selection
    if metric_names is None:
        metric_names = st.multiselect(
            "Select Metrics",
            options=list(METRIC_CONFIGS.keys()),
            default=["Blood Pressure"]
        )
    
    if not metric_names:
        st.info("Select at least one metric to display")
        return
    
    # Time range selection
    col1, col2 = st.columns([3, 1])
    with col1:
        days = st.slider("Time Range", min_value=7, max_value=365, value=30, step=7)
    
    # Fetch and display data
    for metric_name in metric_names:
        st.markdown(f"### {METRIC_CONFIGS[metric_name]['icon']} {metric_name}")
        
        # Fetch data
        url = f"{api_base_url}/api/patients/{patient_id}/metrics"
        params = {"metric_name": metric_name, "limit": days}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            records = response.json()
            
            if not records:
                st.warning(f"No data available for {metric_name}")
                continue
            
            # Prepare data for plotting
            dates = []
            values = []
            value_strings = []
            
            for record in reversed(records):  # Oldest first
                dates.append(datetime.fromisoformat(record["measured_at"]))
                
                if record.get("component_1") and record.get("component_2"):
                    # Composite value (Blood Pressure)
                    value_strings.append(record["value_string"])
                    values.append({
                        "systolic": record["component_1"]["value"],
                        "diastolic": record["component_2"]["value"]
                    })
                else:
                    values.append(record.get("value_numeric") or 0)
                    value_strings.append(str(record.get("value_numeric", "")))
            
            # Create visualization
            if values and isinstance(values[0], dict):
                # Composite metric (Blood Pressure)
                fig = create_bp_chart(dates, values, metric_name)
            else:
                # Simple numeric metric
                fig = create_line_chart(dates, values, metric_name)
            
            st.plotly_chart(fig, use_container_width=True)
            
            # Show data table
            with st.expander("📋 View Raw Data"):
                st.dataframe(
                    {
                        "Date": [d.strftime("%Y-%m-%d %H:%M") for d in dates],
                        "Value": value_strings,
                        "Source": [r.get("source", "unknown") for r in records]
                    }
                )
        
        except Exception as e:
            st.error(f"Failed to load data: {str(e)}")


def create_line_chart(dates, values, metric_name):
    """Create line chart for simple metrics"""
    import plotly.graph_objects as go
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=dates,
        y=values,
        mode="lines+markers",
        name=metric_name,
        line=dict(color="#1f77b4", width=2),
        marker=dict(size=8)
    ))
    
    fig.update_layout(
        title=f"{metric_name} Over Time",
        xaxis_title="Date",
        yaxis_title="Value",
        hovermode="x unified",
        showlegend=False
    )
    
    return fig


def create_bp_chart(dates, values, metric_name, component_names=None):
    """
    Create blood pressure chart with dynamic component lines
    
    Args:
        dates: List of datetime objects
        values: List of dicts with component values
        metric_name: Name of the metric
        component_names: List of component names for legend (e.g., ["Systolic", "Diastolic"])
    """
    import plotly.graph_objects as go

    fig = go.Figure()
    
    # Determine component names from data if not provided
    if not component_names and values:
        component_names = list(values[0].keys())
    
    # Default names if still not available
    if not component_names:
        component_names = ["Component 1", "Component 2"]
    
    # Create a line for each component
    colors = ["#d62728", "#1f77b4", "#2ca02c", "#ff7f0e", "#9467bd"]  # Extended color palette
    
    for i, comp_name in enumerate(component_names):
        comp_values = [v.get(comp_name, 0) for v in values]
        color = colors[i % len(colors)]
        
        fig.add_trace(go.Scatter(
            x=dates,
            y=comp_values,
            mode="lines+markers",
            name=comp_name,
            line=dict(color=color, width=2),
            marker=dict(size=8)
        ))

    fig.update_layout(
        title=f"{metric_name} Over Time",
        xaxis_title="Date",
        yaxis_title="Value",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02)
    )

    return fig


def render_metric_trend(
    patient_id: str,
    api_base_url: str,
    metric_name: str,
    days: int = 30
):
    """
    Render metric trend analysis
    
    Args:
        patient_id: Current patient ID
        api_base_url: Backend API base URL
        metric_name: Name of metric to analyze
        days: Analysis window
    """
    url = f"{api_base_url}/api/patients/{patient_id}/metrics/trend/{metric_name}"
    params = {"days": days}
    
    try:
        response = requests.get(url, params=params)
        response.raise_for_status()
        trend = response.json()
        
        if trend.get("status") == "insufficient_data":
            st.warning(f"⚠️ Insufficient data for trend analysis (need at least 3 data points)")
            return
        
        # Display trend
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric(
                "Trend Direction",
                trend["trend"]["direction"].title(),
                delta=None
            )
        
        with col2:
            slope = trend["trend"]["slope"]
            st.metric(
                "Slope",
                f"{slope:.4f}",
                delta="↑" if slope > 0.01 else ("↓" if slope < -0.01 else "→")
            )
        
        with col3:
            st.metric(
                "Data Points",
                trend["statistics"]["data_point_count"]
            )
        
        # Display statistics
        st.markdown("#### Statistics")
        stats_col1, stats_col2, stats_col3 = st.columns(3)
        
        with stats_col1:
            st.metric("Average", f"{trend['statistics']['average']:.1f}")
        
        with stats_col2:
            st.metric("Min", f"{trend['statistics']['min']:.1f}")
        
        with stats_col3:
            st.metric("Max", f"{trend['statistics']['max']:.1f}")
        
    except Exception as e:
        st.error(f"Failed to load trend: {str(e)}")
