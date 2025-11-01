"""
Streamlit Dashboard for Real-time TDS Monitoring
Displays live TDS readings from multiple devices with charts and alerts
"""
import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from datetime import datetime, timedelta
import yaml
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.append(str(Path(__file__).parent.parent))
from utils.storage import (
    last_n_readings, 
    get_latest_by_device, 
    export_csv, 
    get_stats,
    get_device_list
)

# Page configuration
st.set_page_config(
    page_title="TDS Monitor Dashboard",
    page_icon="💧",
    layout="wide",
    initial_sidebar_state="expanded"
)

def load_config():
    """Load configuration"""
    try:
        with open("config.yaml", "r") as f:
            return yaml.safe_load(f)
    except:
        return {
            'thresholds': {'good': 300, 'moderate': 600},
            'dashboard': {'refresh_interval': 1.5, 'default_time_window': 30}
        }

def get_water_quality_status(tds, thresholds):
    """Determine water quality status based on TDS value"""
    if tds < thresholds['good']:
        return "Good", "🟢", "#28a745"
    elif tds < thresholds['moderate']:
        return "Moderate", "🟡", "#ffc107"
    else:
        return "Poor", "🔴", "#dc3545"

def create_gauge_chart(tds, thresholds):
    """Create a gauge chart for TDS value"""
    status, icon, color = get_water_quality_status(tds, thresholds)
    
    fig = go.Figure(go.Indicator(
        mode="gauge+number+delta",
        value=tds,
        domain={'x': [0, 1], 'y': [0, 1]},
        title={'text': f"TDS (ppm) {icon}", 'font': {'size': 24}},
        delta={'reference': thresholds['good'], 'increasing': {'color': "red"}},
        gauge={
            'axis': {'range': [None, 1000], 'tickwidth': 1, 'tickcolor': "darkblue"},
            'bar': {'color': color},
            'bgcolor': "white",
            'borderwidth': 2,
            'bordercolor': "gray",
            'steps': [
                {'range': [0, thresholds['good']], 'color': '#d4edda'},
                {'range': [thresholds['good'], thresholds['moderate']], 'color': '#fff3cd'},
                {'range': [thresholds['moderate'], 1000], 'color': '#f8d7da'}
            ],
            'threshold': {
                'line': {'color': "red", 'width': 4},
                'thickness': 0.75,
                'value': thresholds['moderate']
            }
        }
    ))
    
    fig.update_layout(height=300, margin=dict(l=20, r=20, t=60, b=20))
    return fig

def create_tds_chart(df, device_id=None):
    """Create time-series chart for TDS readings"""
    fig = go.Figure()
    
    if device_id:
        # Single device
        device_df = df[df['device_id'] == device_id]
        fig.add_trace(go.Scatter(
            x=device_df['timestamp'],
            y=device_df['tds'],
            mode='lines+markers',
            name=device_id,
            line=dict(width=2),
            marker=dict(size=6)
        ))
    else:
        # Multiple devices
        for device in df['device_id'].unique():
            device_df = df[df['device_id'] == device]
            fig.add_trace(go.Scatter(
                x=device_df['timestamp'],
                y=device_df['tds'],
                mode='lines+markers',
                name=device,
                line=dict(width=2),
                marker=dict(size=6)
            ))
    
    fig.update_layout(
        title="TDS Over Time",
        xaxis_title="Time",
        yaxis_title="TDS (ppm)",
        hovermode='x unified',
        height=400,
        margin=dict(l=50, r=20, t=60, b=50)
    )
    
    return fig

# Load config
config = load_config()
thresholds = config['thresholds']
refresh_interval = config['dashboard']['refresh_interval']
default_window = config['dashboard']['default_time_window']

# Header
st.title("💧 Real-Time TDS Monitor Dashboard")
st.markdown("---")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    
    # Time window selector
    time_options = {
        "Last 5 minutes": 5,
        "Last 15 minutes": 15,
        "Last 30 minutes": 30,
        "Last 1 hour": 60,
        "Last 6 hours": 360,
        "Last 24 hours": 1440,
        "All data": None
    }
    
    selected_time = st.selectbox(
        "Time Window",
        options=list(time_options.keys()),
        index=2  # Default to 30 minutes
    )
    time_window = time_options[selected_time]
    
    # Device filter
    devices = get_device_list()
    device_options = ["All Devices"] + [d[0] for d in devices]
    selected_device = st.selectbox("Filter Device", device_options)
    device_filter = None if selected_device == "All Devices" else selected_device
    
    st.markdown("---")
    
    # Threshold display
    st.subheader("🎯 Thresholds")
    st.success(f"Good: < {thresholds['good']} ppm")
    st.warning(f"Moderate: {thresholds['good']}-{thresholds['moderate']} ppm")
    st.error(f"Poor: > {thresholds['moderate']} ppm")
    
    st.markdown("---")
    
    # Export button
    if st.button("📥 Export CSV", use_container_width=True):
        export_path = export_csv(device_id=device_filter)
        if export_path:
            st.success(f"Exported to {export_path}")
        else:
            st.warning("No data to export")
    
    # Stats
    st.markdown("---")
    st.subheader("📊 Statistics")
    stats = get_stats()
    st.metric("Total Readings", stats['total_readings'])
    st.metric("Total Devices", stats['total_devices'])
    
    # Refresh indicator
    st.markdown("---")
    st.caption(f"🔄 Auto-refresh: {refresh_interval}s")
    st.caption(f"🕐 Last update: {datetime.now().strftime('%H:%M:%S')}")

# Main content area
# Get latest data for all devices
latest_devices = get_latest_by_device()

if latest_devices.empty:
    st.warning("⚠️ No data received yet. Waiting for devices to connect...")
    st.info("""
    **Getting Started:**
    1. Start the HTTP server: `python -m ingest.http_server`
    2. Or start serial ingestion: `python -m ingest.serial_ingest`
    3. Configure your ESP32/Arduino to send data
    4. Data will appear here automatically
    """)
else:
    # Device cards at the top
    st.subheader("📡 Connected Devices")
    
    cols = st.columns(min(len(latest_devices), 4))
    
    for idx, row in latest_devices.iterrows():
        col_idx = idx % len(cols)
        with cols[col_idx]:
            device_id = row['device_id']
            tds = row['tds']
            device_ip = row['device_ip'] or "N/A"
            last_seen = row['timestamp']
            
            status, icon, color = get_water_quality_status(tds, thresholds)
            
            # Time since last reading
            time_diff = datetime.now() - last_seen
            seconds_ago = int(time_diff.total_seconds())
            
            if seconds_ago < 60:
                time_str = f"{seconds_ago}s ago"
            elif seconds_ago < 3600:
                time_str = f"{seconds_ago // 60}m ago"
            else:
                time_str = f"{seconds_ago // 3600}h ago"
            
            # Device card
            with st.container():
                st.markdown(f"""
                <div style="border: 2px solid {color}; border-radius: 10px; padding: 15px; background-color: rgba(255,255,255,0.05);">
                    <h3 style="margin: 0; color: {color};">{icon} {device_id}</h3>
                    <h1 style="margin: 10px 0; font-size: 2.5em;">{tds:.1f} <small style="font-size: 0.4em;">ppm</small></h1>
                    <p style="margin: 5px 0;"><strong>Status:</strong> {status}</p>
                    <p style="margin: 5px 0;"><strong>IP:</strong> {device_ip}</p>
                    <p style="margin: 5px 0; color: #888;"><small>Updated: {time_str}</small></p>
                </div>
                """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # Get historical data
    df = last_n_readings(minutes=time_window, device_id=device_filter)
    
    if not df.empty:
        # Two columns: Gauge and Chart
        col1, col2 = st.columns([1, 2])
        
        with col1:
            st.subheader("Current Reading")
            # Show gauge for selected device or latest from all
            if device_filter:
                gauge_data = latest_devices[latest_devices['device_id'] == device_filter]
                if not gauge_data.empty:
                    gauge_tds = gauge_data.iloc[0]['tds']
                    st.plotly_chart(create_gauge_chart(gauge_tds, thresholds), use_container_width=True)
            else:
                # Show latest overall
                latest_tds = latest_devices.iloc[0]['tds']
                st.plotly_chart(create_gauge_chart(latest_tds, thresholds), use_container_width=True)
        
        with col2:
            st.subheader("Trends")
            st.plotly_chart(create_tds_chart(df, device_filter), use_container_width=True)
        
        # Data table
        st.markdown("---")
        st.subheader("📋 Recent Readings")
        
        # Format the dataframe for display
        display_df = df[['timestamp', 'device_id', 'device_ip', 'tds', 'voltage']].tail(50).copy()
        display_df['timestamp'] = display_df['timestamp'].dt.strftime('%Y-%m-%d %H:%M:%S')
        display_df['tds'] = display_df['tds'].round(2)
        
        # Add status column
        display_df['status'] = display_df['tds'].apply(
            lambda x: get_water_quality_status(x, thresholds)[0]
        )
        
        # Reorder columns
        display_df = display_df[['timestamp', 'device_id', 'device_ip', 'tds', 'voltage', 'status']]
        
        st.dataframe(
            display_df.iloc[::-1],  # Reverse to show newest first
            use_container_width=True,
            hide_index=True
        )
    else:
        st.info(f"No data available for the selected time window ({selected_time})")

# Auto-refresh
st.rerun()