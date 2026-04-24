import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import datetime
from database import conn

def render_analytics_dashboard():
    st.markdown("### 📈 Live Event Analytics")
    
    # 1. Fetch fresh data
    df = conn.query("SELECT * FROM guests", ttl=0)
    
    if df.empty:
        st.info("No guest data available to analyze yet.")
        return
    
    # Pre-process Data (handling potential NaNs/Nulls gracefully)
    df['assigned_gre'] = df['assigned_gre'].fillna('Unassigned').replace(['', 'None', '-- Unassigned --'], 'Unassigned')
    df['speaker_category'] = df['speaker_category'].fillna('Non-Speaker').replace('', 'Non-Speaker')
    df['room_cleaned'] = pd.to_numeric(df['room_cleaned'], errors='coerce').fillna(0)
    df['airport_pickup_sent'] = pd.to_numeric(df['airport_pickup_sent'], errors='coerce').fillna(0)
    
    # Convert arrival times to datetimes for tracking "Arrivals Today"
    today_str = datetime.date.today().strftime('%Y-%m-%d')
    df['parsed_arrival'] = pd.to_datetime(df['arrival_time'], errors='coerce')
    arrivals_today = len(df[df['parsed_arrival'].dt.strftime('%Y-%m-%d') == today_str])

    # 2. Top-Level KPI Row
    total_guests = len(df)
    unassigned_guests = len(df[df['assigned_gre'] == 'Unassigned'])
    pending_pickups = len(df[df['airport_pickup_sent'] == 0])
    
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(label="👥 Total Guests", value=total_guests)
    c2.metric(label="🛬 Arriving Today", value=arrivals_today)
    
    # Red alert for unassigned guests if > 0
    c3.metric(label="⚠️ Unassigned GRE", value=unassigned_guests, 
              delta="- Action Needed" if unassigned_guests > 0 else "All Assigned", delta_color="inverse")
    
    c4.metric(label="🚗 Pending Pickups", value=pending_pickups)

    st.divider()

    # 3. Visual Charts Row 1
    col_chart1, col_chart2 = st.columns(2)
    
    with col_chart1:
        st.markdown("**🏨 Housing Readiness**")
        cleaned_count = len(df[df['room_cleaned'] == 1])
        dirty_count = total_guests - cleaned_count
        
        # Plotly Donut Chart
        fig_housing = px.pie(
            values=[cleaned_count, dirty_count], 
            names=['Ready / Cleaned', 'Pending / Dirty'],
            hole=0.5,
            color_discrete_sequence=['#22c55e', '#ef4444'] # Green and Red
        )
        fig_housing.update_layout(margin=dict(t=20, b=20, l=20, r=20), showlegend=True)
        st.plotly_chart(fig_housing, use_container_width=True)

    with col_chart2:
        st.markdown("**🎙️ Guest Categories**")
        speaker_counts = df['speaker_category'].value_counts().reset_index()
        speaker_counts.columns = ['Category', 'Count']
        
        fig_speakers = px.bar(
            speaker_counts, 
            x='Category', 
            y='Count',
            text='Count',
            color='Category',
            color_discrete_sequence=['#3b82f6', '#f59e0b'] # Blue and Amber
        )
        fig_speakers.update_traces(textposition='outside')
        fig_speakers.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title="", yaxis_title="Number of Guests", showlegend=False)
        st.plotly_chart(fig_speakers, use_container_width=True)

    st.divider()

    # 4. Team Workload Chart
    st.markdown("**🛎️ GRE Workload Distribution**")
    
    gre_counts = df[df['assigned_gre'] != 'Unassigned']['assigned_gre'].value_counts().reset_index()
    gre_counts.columns = ['GRE Name', 'Guests Assigned']
    
    if not gre_counts.empty:
        fig_gre = px.bar(
            gre_counts, 
            x='GRE Name', 
            y='Guests Assigned',
            text='Guests Assigned',
            color='Guests Assigned',
            color_continuous_scale='Blues'
        )
        fig_gre.update_traces(textposition='outside')
        fig_gre.update_layout(margin=dict(t=20, b=20, l=20, r=20), xaxis_title="Staff Member", yaxis_title="Total Assigned Guests")
        st.plotly_chart(fig_gre, use_container_width=True)
    else:
        st.info("No guests have been assigned to GREs yet.")
