import streamlit as st
import pandas as pd

# Import the core functions directly from your main file
from main import fetch_all_guests, ddp_dialog, alerts_overview_dialog

# Set a mobile-friendly page config
st.set_page_config(page_title="Mobile Directory", page_icon="📱", layout="centered")

raw_df = fetch_all_guests()

# Defensive Column Check
expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 'departure_time', 'housing', 'gift_type', 'ashram_tour']
for col in expected:
    if col not in raw_df.columns: raw_df[col] = None 

if not raw_df.empty:
    raw_df['arrival_dt'] = pd.to_datetime(raw_df['arrival_time'], format='%d/%m/%Y %H:%M', errors='coerce')
    raw_df = raw_df.sort_values(by=['arrival_dt', 'name'], ascending=[True, True], na_position='last')
    raw_df['category'] = raw_df['category'].apply(lambda x: str(x).strip().title() if pd.notna(x) and str(x).strip() else None)

# --- MOBILE HEADER ---
st.markdown("### 📱 Mobile Admin Directory")

all_guests = sorted([str(x) for x in raw_df['name'].dropna().unique() if str(x).strip()])
all_pocs = sorted([str(x) for x in raw_df['poc'].dropna().unique() if str(x).strip()])
available_cats = sorted(list(set([str(x) for x in raw_df['category'].dropna() if str(x).strip()])))

# --- VERTICAL SEARCH UI (Thumb-Friendly) ---
with st.container(border=True):
    st.markdown("<span class='mobile-search-target'></span>", unsafe_allow_html=True)
    # Everything is stacked vertically, no columns
    s_name = st.selectbox("**👤 Find Guest Name**", options=all_guests, index=None, placeholder="Start typing...", key="m_name_input")
    s_poc = st.multiselect("**📞 POC**", options=all_pocs, placeholder="Select...", key="m_poc_input")
    
    with st.expander("🛠️ Filters (Category, Date, Unassigned)"):
        s_cat = st.multiselect("**🏷️ Category**", options=available_cats, key="m_cat")
        s_date = st.date_input("**📅 Arrival Date**", value=[], key="m_date")
        s_unassigned = st.checkbox("**🚨 Show ONLY Unassigned GRE**", key="m_unassigned")

# --- FILTERING LOGIC ---
filtered_df = raw_df.copy()
if s_name: filtered_df = filtered_df[filtered_df['name'] == s_name]
if s_poc: filtered_df = filtered_df[filtered_df['poc'].isin(s_poc)]
if s_cat: filtered_df = filtered_df[filtered_df['category'].isin(s_cat)]
    
if len(s_date) == 2:
    start_date, end_date = s_date
    filtered_df = filtered_df[(filtered_df['arrival_dt'].dt.date >= start_date) & (filtered_df['arrival_dt'].dt.date <= end_date)]
elif len(s_date) == 1:
    filtered_df = filtered_df[filtered_df['arrival_dt'].dt.date == s_date[0]]
    
if s_unassigned:
    filtered_df = filtered_df[filtered_df['assigned_gre'].isna() | filtered_df['assigned_gre'].str.strip().isin(["", "-- Unassigned --", "None"])]

# --- ALERTS & STYLING ---
alerts_list = [{"Guest": row['name'], "Alert(s)": "GRE Not Assigned", "POC": row['poc']} 
               for _, row in filtered_df.iterrows() 
               if pd.isna(row['assigned_gre']) or str(row['assigned_gre']).strip() in ["", "-- Unassigned --", "None"]]
alerts_df = pd.DataFrame(alerts_list)
num_alerts = len(alerts_df)

st.markdown("""
    <style>
    div[data-testid="stVerticalBlockBorderWrapper"]:has(.mobile-search-target) { 
        background-color: #FFF9C4 !important; border: 2px solid #FBC02D !important;
    }
    div.element-container:has(.btn-red-target) + div.element-container button { 
        background-color: #ff4b4b !important; color: white !important; border: none !important; 
    }
    div.element-container:has(.btn-green-target) + div.element-container button { 
        background-color: #04AA6D !important; color: white !important; border: none !important; 
    }
    </style>
""", unsafe_allow_html=True)

# --- MOBILE ACTION BAR ---
if not filtered_df.empty:
    total = len(filtered_df)
    pending = len(alerts_list)
    
    # Stacked mobile metrics
    st.info(f"**Results:** {total} Guests | **🚨 Pending:** {pending}")
    
    # Massive, thumb-friendly alerts button
    if num_alerts > 0:
        st.markdown("<span class='btn-red-target'></span>", unsafe_allow_html=True)
        if st.button(f"🔴 VIEW ALERTS ({num_alerts})", use_container_width=True, key="m_alert_red"):
            alerts_overview_dialog(alerts_df)
    else:
        st.markdown("<span class='btn-green-target'></span>", unsafe_allow_html=True)
        if st.button("🟢 ALERTS (0)", use_container_width=True, key="m_alert_grn"):
            alerts_overview_dialog(alerts_df)
    
    st.divider()

    # --- MOBILE PERFORMANCE GATE & CARDS ---
    if total > 50:
        st.warning("⚠️ **List too long for mobile view.**\nPlease use the search tools above to narrow the results down to 50 or fewer guests.")
    else:
        for _, row in filtered_df.iterrows():
            # A compact, vertical card design
            with st.container(border=True):
                st.markdown(f"#### {row['name']}")
                st.caption(f"🕒 **Arr:** {row['arrival_time']} | 📞 **POC:** {row['poc']}")
                
                if pd.isna(row['assigned_gre']) or str(row['assigned_gre']).strip() in ["", "-- Unassigned --", "None"]:
                    st.markdown(":red[**🚨 GRE NOT ASSIGNED**]")
                else:
                    st.write(f"👔 **GRE:** {row['assigned_gre']}")
                    
                # Massive action button at the bottom of the card
                if st.button(f"📂 Open Details", key=f"m_btn_{row['id']}", use_container_width=True):
                    ddp_dialog(row.to_dict())
