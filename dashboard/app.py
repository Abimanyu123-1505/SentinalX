"""
SentinelX Live Dashboard (Streamlit)

Displays real‑time risk scores, anomaly alerts, and session summary.
Polls the FastAPI backend (SQLite) to retrieve the most recent risk records.

Privacy: No raw interaction data is displayed – only aggregated risk metrics.
All data shown is derived from timing metadata only.
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from sqlalchemy import create_engine, text
import os
import sys
import time
import json
from datetime import datetime

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Page configuration - MUST be the first Streamlit command
st.set_page_config(
    page_title="SentinelX Proctoring Dashboard",
    page_icon="🛡️",
    layout="wide"
)

# Custom CSS for better visibility
st.markdown("""
<style>
    .risk-high { color: #ff4b4b; font-weight: bold; }
    .risk-medium { color: #ffa64b; font-weight: bold; }
    .risk-low { color: #4bff4b; font-weight: bold; }
    .alert-box {
        padding: 10px;
        border-radius: 5px;
        margin: 5px 0;
        background-color: #f0f2f6;
    }
</style>
""", unsafe_allow_html=True)

# Title
st.title("🛡️ SentinelX – Real‑time Risk Dashboard")
st.markdown("**Privacy‑first proctoring:** only timing metadata, no keystroke content.")

# Initialize session state
if 'refresh_count' not in st.session_state:
    st.session_state.refresh_count = 0
if 'last_data_hash' not in st.session_state:
    st.session_state.last_data_hash = None

# Database connection
@st.cache_resource
def get_engine():
    """Create SQLAlchemy engine for SQLite."""
    db_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "sentinelx.db")
    engine_url = f"sqlite:///{db_path}"
    return create_engine(engine_url, connect_args={"check_same_thread": False})

engine = get_engine()

# Sidebar controls
with st.sidebar:
    st.header("Controls")
    refresh_rate = st.slider("Refresh interval (seconds)", 1, 10, 2)
    max_records = st.slider("Number of records to display", 10, 100, 50)
    
    st.header("Session Selection")
    # Get all distinct session IDs
    try:
        with engine.connect() as conn:
            result = conn.execute(text("SELECT DISTINCT session_id FROM risk_records ORDER BY session_id"))
            session_list = [row[0] for row in result.fetchall()]
        selected_session = st.selectbox("Filter by session ID", ["All"] + session_list if session_list else ["All"])
    except Exception:
        selected_session = "All"
    
    st.markdown("---")
    st.markdown("**System Info**")
    st.markdown(f"Database: `sentinelx.db`")
    
    # Manual refresh button
    if st.button("🔄 Manual Refresh"):
        st.session_state.refresh_count += 1
        st.rerun()

# Main dashboard layout
col1, col2 = st.columns([2, 1])

# Placeholders for dynamic content
risk_graph_placeholder = col1.empty()
alert_placeholder = col2.empty()
summary_placeholder = st.empty()

# Auto-refresh logic
time.sleep(0.1)

try:
    # Build query
    if selected_session != "All":
        query = text("SELECT * FROM risk_records WHERE session_id = :session_id ORDER BY timestamp DESC LIMIT :limit")
        params = {"session_id": selected_session, "limit": max_records}
    else:
        query = text("SELECT * FROM risk_records ORDER BY timestamp DESC LIMIT :limit")
        params = {"limit": max_records}
    
    # Fetch latest data
    with engine.connect() as conn:
        result = conn.execute(query, params)
        rows = result.fetchall()
        if rows:
            # Convert to DataFrame with explicit dtypes
            df = pd.DataFrame(rows, columns=result.keys())
            # Ensure risk_score is float
            df['risk_score'] = pd.to_numeric(df['risk_score'], errors='coerce').fillna(0.0)
        else:
            df = pd.DataFrame()
    
    if df.empty:
        risk_graph_placeholder.info("No risk records found. Waiting for data...")
        alert_placeholder.info("No alerts yet.")
        summary_placeholder.info("No session summary available.")
    else:
        # Convert timestamp column to datetime
        df['datetime'] = pd.to_datetime(df['timestamp'], unit='s')
        
        # --- Live Risk Graph ---
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=df['datetime'],
            y=df['risk_score'],
            mode='lines+markers',
            name='Risk Score',
            line=dict(color='#1f77b4', width=2),
            marker=dict(size=6)
        ))
        
        # Add threshold lines
        fig.add_hline(y=30, line_dash="dash", line_color="green", annotation_text="Low")
        fig.add_hline(y=60, line_dash="dash", line_color="orange", annotation_text="Medium")
        fig.add_hline(y=80, line_dash="dash", line_color="red", annotation_text="High")
        
        fig.update_layout(
            title="Risk Score Over Time",
            xaxis_title="Time",
            yaxis_title="Risk Score (0–100)",
            yaxis=dict(range=[0, 100]),
            height=400,
            margin=dict(l=0, r=0, t=40, b=0)
        )
        
        # FIXED: Use width='stretch' instead of use_container_width
        risk_graph_placeholder.plotly_chart(
            fig, 
            width='stretch',
            key=f"risk_chart_{st.session_state.refresh_count}_{len(df)}"
        )
        
        # --- Alert Log ---
        alerts = []
        for _, row in df.iterrows():
            risk = row['risk_score']
            if risk >= 80:
                level = "🔴 HIGH"
            elif risk >= 60:
                level = "🟠 MEDIUM"
            elif risk >= 30:
                level = "🟡 LOW"
            else:
                continue  # no alert
            
            # Parse anomaly scores (JSON stored as string)
            try:
                scores = json.loads(row['anomaly_scores'])
                idle = scores.get('idle_burst', 0)
                focus = scores.get('focus_instability', 0)
                drift = scores.get('behavioral_drift', 0)
            except:
                idle = focus = drift = 0
            
            alert_text = f"**{level}** Risk: {risk:.1f}  \nSession: {row['session_id'][:8]}...  \nAnomalies: I:{idle:.0f} F:{focus:.0f} D:{drift:.0f}  \nTime: {row['datetime'].strftime('%H:%M:%S')}"
            alerts.append(alert_text)
        
        if alerts:
            alert_placeholder.markdown("### 🚨 Alert Log\n" + "\n---\n".join(alerts[:10]))
        else:
            alert_placeholder.markdown("### ✅ No active alerts")
        
        # --- Session Summary - FIXED: Convert values to strings to avoid Arrow serialization issues ---
        if selected_session != "All":
            session_df = df[df['session_id'] == selected_session]
        else:
            session_df = df
        
        # Ensure we have numeric values
        if not session_df.empty:
            avg_risk = session_df['risk_score'].mean()
            max_risk = session_df['risk_score'].max()
            min_risk = session_df['risk_score'].min()
            latest_risk = session_df.iloc[0]['risk_score']
        else:
            avg_risk = max_risk = min_risk = latest_risk = 0.0
        
        # FIXED: Create summary with ALL values as strings to avoid Arrow type conversion issues
        summary = {
            "Total risk records": str(len(session_df)),
            "Average risk": f"{avg_risk:.1f}",
            "Max risk": f"{max_risk:.1f}",
            "Min risk": f"{min_risk:.1f}",
            "Latest risk": f"{latest_risk:.1f}",
        }
        
        # Create summary DataFrame with explicit string type
        summary_df = pd.DataFrame(list(summary.items()), columns=["Metric", "Value"])
        summary_df['Value'] = summary_df['Value'].astype(str)
        
        summary_placeholder.markdown("### 📊 Session Summary")
        summary_placeholder.table(summary_df)
        
except Exception as e:
    st.error(f"Dashboard error: {str(e)}")