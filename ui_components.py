import streamlit as st
import pandas as pd
from sqlalchemy import text
import datetime
import urllib.parse
import re
from database import conn

# --- SILENT DATABASE SAVE CALLBACKS ---
def db_update(field, widget_key, gid):
    val = st.session_state[widget_key]
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": val, "id": gid})
        s.commit()
    st.toast(f"✅ Saved!", icon="💾")

def db_update_datetime(field, date_key, time_key, gid):
    d_val = st.session_state[date_key]
    t_val = st.session_state[time_key]
    final_dt = f"{d_val.strftime('%d/%m/%Y')} {t_val.strftime('%H:%M')}"
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": final_dt, "id": gid})
        s.commit()
    st.toast(f"✅ Time Saved!", icon="⏱️")

def parse_dt(dt_str):
    if not dt_str or pd.isna(dt_str) or str(dt_str).strip() in ["", "TBD"]:
        return datetime.date.today(), datetime.time(12, 0)
    try:
        dt_obj = datetime.datetime.strptime(str(dt_str).strip(), "%d/%m/%Y %H:%M")
        return dt_obj.date(), dt_obj.time()
    except:
        return datetime.date.today(), datetime.time(12, 0)


@st.dialog("DDP - Dignitary Details Page", width="large")
def ddp_dialog(guest_data):
    gid = guest_data['id']
    st.subheader(f"👤 {guest_data['name']}")
    
    # --- 1. AT-A-GLANCE STATUS BAR ---
    rm_icon = "🟩 Room Cleaned" if guest_data.get('room_cleaned') else "🟨 Room Pending"
    pk_icon = "🟩 Pickup Sent" if guest_data.get('airport_pickup_sent') else "🟨 Pickup Pending"
    
    gre_val = guest_data.get('assigned_gre')
    gre_icon = "🟩 GRE Assigned" if pd.notna(gre_val) and str(gre_val).strip() not in ["", "None", "-- Unassigned --"] else "🟥 GRE Unassigned"
    
    st.markdown(f"#### `{rm_icon}` ｜ `{pk_icon}` ｜ `{gre_icon}`")
    st.caption("✨ *Inline Editing Enabled: Type and press Enter or click away to save instantly.*")
    st.divider()
    
    info_c1, info_c2, info_c3 = st.columns(3)
    
    with info_c1:
        st.markdown("### 🪪 Profile")
        
        cat_label = "Category 🚨" if not guest_data.get('category') or str(guest_data.get('category')).strip() == "" else "Category"
        st.text_input(cat_label, value=guest_data.get('category', ''), key=f"cat_{gid}", 
                      on_change=db_update, args=("category", f"cat_{gid}", gid))
        
        st.selectbox("Speaker Status", ["Speaker", "Non-Speaker"], 
                     index=0 if guest_data.get('speaker_category') == "Speaker" else 1,
                     key=f"spk_{gid}", on_change=db_update, args=("speaker_category", f"spk_{gid}", gid))
        
        st.number_input("Accompanying Pax", min_value=0, 
                        value=int(guest_data.get('accompanying_persons', 0)) if pd.notna(guest_data.get('accompanying_persons')) else 0,
                        key=f"pax_{gid}", on_change=db_update, args=("accompanying_persons", f"pax_{gid}", gid))
        
        poc_label = "POC Name 🚨" if not guest_data.get('poc') or str(guest_data.get('poc')).strip() == "" else "POC Name"
        st.text_input(poc_label, value=guest_data.get('poc', ''), key=f"poc_{gid}",
                      on_change=db_update, args=("poc", f"poc_{gid}", gid))

    with info_c2:
        st.markdown("### ✈️ Logistics")
        
        hou_label = "Housing / Room 🚨" if guest_data.get('housing') in ["TBD", "", None] else "Housing / Room"
        st.text_input(hou_label, value=guest_data.get('housing', 'TBD'), key=f"hou_{gid}",
                      on_change=db_update, args=("housing", f"hou_{gid}", gid))
        
        # GRE Assignment Logic
        gre_df = conn.query("SELECT gre_name FROM gres", ttl=0)
        avail_gres = ["-- Unassigned --"] + gre_df['gre_name'].tolist() if not gre_df.empty else ["-- Unassigned --"]
        current_gre = guest_data.get('assigned_gre') if pd.notna(guest_data.get('assigned_gre')) and str(guest_data.get('assigned_gre')).strip() not in ["", "None"] else "-- Unassigned --"
        if current_gre not in avail_gres: avail_gres.append(current_gre)
        
        def update_gre(widget_key, gid):
            val = st.session_state[widget_key]
            v = None if val == "-- Unassigned --" else val
            with conn.session as s:
                s.execute(text("UPDATE guests SET assigned_gre = :v WHERE id = :id"), {"v": v, "id": gid})
                s.commit()
            st.toast("✅ GRE Assigned!", icon="🤝")

        gre_label = "Assigned GRE 🚨" if current_gre == "-- Unassigned --" else "Assigned GRE"
        st.selectbox(gre_label, avail_gres, index=avail_gres.index(current_gre),
                     key=f"gre_{gid}",
