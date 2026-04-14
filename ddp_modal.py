import streamlit as st
import pandas as pd
import urllib.parse
import re
from sqlalchemy import text
from database import conn
from utils import parse_dt, format_for_wa
from callbacks import (db_update, db_update_datetime, update_gre_cb, toggle_room_cb, 
                       toggle_pk_cb, toggle_ashram_cb, toggle_pin_cb, add_guest_note_cb)

@st.dialog("DDP - Dignitary Details Page", width="large")
def ddp_dialog(guest_data_input):
    gid = guest_data_input['id']
    
    try:
        fresh_df = conn.query("SELECT * FROM guests WHERE id = :id", params={"id": gid}, ttl=0)
        guest_data = fresh_df.iloc[0].to_dict() if not fresh_df.empty else guest_data_input
    except:
        guest_data = guest_data_input

    name = guest_data.get('name', 'Unknown Guest')
    cat = guest_data.get('category', 'Unassigned')
    speaker = guest_data.get('speaker_category', '')
    pax = guest_data.get('accompanying_persons', 0)
    pax_val = int(pax) if pd.notna(pax) and str(pax).isdigit() else (pax if pd.notna(pax) else 0)

    badges = [f'<span class="ddp-badge">🏷️ {cat}</span>']
    if speaker == 'Speaker': badges.append('<span class="ddp-badge ddp-badge-speaker">🎙️ Speaker</span>')
    badges.append(f'<span class="ddp-badge">👥 +{pax_val} Accompanying</span>')
    badges_html = "".join(badges)

    is_pinned = bool(guest_data.get('remarks_pinned', 0))
    raw_remarks = guest_data.get('remarks', '')
    clean_remarks = '' if pd.isna(raw_remarks) or raw_remarks is None else str(raw_remarks)
    
    pinned_html = ""
    if is_pinned and clean_remarks.strip():
        html_remarks = clean_remarks.replace('\n', '<br>')
        pinned_html = f"<div style='background-color: #fee2e2; border-left: 4px solid #ef4444; padding: 12px; margin-top: 15px; border-radius: 4px; color: #991b1b; font-size: 14px;'><strong>📌 Pinned Note:</strong><br>{html_remarks}</div>"

    st.markdown(f"""
    <style>
    .ddp-header {{ background-color: #f8f9fa; padding: 20px; border-radius: 10px; margin-bottom: 20px; border-left: 6px solid #0068c9; }}
    .ddp-title {{ font-size: 26px; font-weight: 800; margin-bottom: 8px; color: #1f2937; }}
    .ddp-badge {{ background-color: #e5e7eb; padding: 6px 10px; border-radius: 6px; font-size: 13px; font-weight: 600; margin-right: 8px; color: #374151; display: inline-block; }}
    .ddp-badge-speaker {{ background-color: #fef08a; color: #854d0e; }}
    </style>
    <div class="ddp-header">
        <div class="ddp-title">{name}</div>
        <div class="ddp-badges-row">{badges_html}</div>
        {pinned_html}
    </div>
    """, unsafe_allow_html=True)

    st.caption("✨ *Inline Editing Enabled: Type and press Enter or click away to save instantly.*")

    t_profile, t_logistics, t_team = st.tabs(["🪪 Profile & Status", "✈️ Logistics & Times", "📞 Team & Comms"])

    with t_profile:
        col_p1, col_p2 = st.columns(2)
        with col_p1:
            st.text_input("Category", value=guest_data.get('category', ''), key=f"cat_{gid}", on_change=db_update, args=("category", f"cat_{gid}", gid))
            st.selectbox("Speaker Status", ["Speaker", "Non-Speaker"], index=0 if guest_data.get('speaker_category') == "Speaker" else 1, key=f"spk_{gid}", on_change=db_update, args=("speaker_category", f"spk_{gid}", gid))
            st.number_input("Accompanying Pax", min_value=0, value=int(guest_data.get('accompanying_persons', 0)) if pd.notna(guest_data.get('accompanying_persons')) else 0, key=f"pax_{gid}", on_change=db_update, args=("accompanying_persons", f"pax_{gid}", gid))
            st.text_input("GIFT Type", value=guest_data.get('gift_type', 'Pending'), key=f"gift_{gid}", on_change=db_update, args=("gift_type", f"gift_{gid}", gid))
        with col_p2:
            st.markdown("#### 🛎️ Ground Status")
            st.toggle("Room Cleaned", value=bool(guest_data.get('room_cleaned', 0)), key=f"ddp_rm_{gid}", on_change=toggle_room_cb, args=(f"ddp_rm_{gid}", gid))
            st.toggle("Pickup Sent", value=bool(guest_data.get('airport_pickup_sent', 0)), key=f"ddp_pk_{gid}", on_change=toggle_pk_cb, args=(f"ddp_pk_{gid}", gid))
            st.toggle("Ashram Tour", value=bool(guest_data.get('ashram_tour', 0)), key=f"ddp_ash_{gid}", on_change=toggle_ashram_cb, args=(f"ddp_ash_{gid}", gid))

    with t_logistics:
        col_l1, col_l2 = st.columns([3, 2])
        with col_l1:
            arr_val = guest_data.get('arrival_time')
            if pd.isna(arr_val) or arr_val is None or str(arr_val).strip() in ["", "None", "TBD", "nan", "NaT"]:
                st.warning("⚠️ Date of Arrival: **Not Assigned**")
                with st.expander("➕ Assign Arrival Date & Time"):
                    c_arr1, c_arr2 = st.columns(2)
                    c_arr1.date_input("Arrival Date", value=None, key=f"arr_d_{gid}", on_change=db_update_datetime, args=("arrival_time", f"arr_d_{gid}", f"arr_t_{gid}", gid))
                    c_arr2.time_input("Arrival Time", value=None, key=f"arr_t_{gid}", on_change=db_update_datetime, args=("arrival_time", f"arr_d_{gid}", f"arr_t_{gid}", gid))
            else:
                arr_d, arr_t = parse_dt(arr_val)
                c_arr1, c_arr2 = st.columns(2)
                c_arr1.date_input("Arrival Date", value=arr_d, format="DD/MM/YYYY", key=f"arr_d_{gid}", on_change=db_update_datetime, args=("arrival_time", f"arr_d_{gid}", f"arr_t_{gid}", gid))
                c_arr2.time_input("Arrival Time", value=arr_t, key=f"arr_t_{gid}", on_change=db_update_datetime, args=("arrival_time", f"arr_d_{gid}", f"arr_t_{gid}", gid))

            st.divider()

            dep_val = guest_data.get('departure_time')
            if pd.isna(dep_val) or dep_val is None or str(dep_val).strip() in ["", "None", "TBD", "nan", "NaT"]:
                st.warning("⚠️ Date of Departure: **Not Assigned**")
                with st.expander("➕ Assign Departure Date & Time"):
                    c_dep1, c_dep2 = st.columns(2)
                    c_dep1.date_input("Departure Date", value=None, key=f"dep_d_{gid}", on_change=db_update_datetime, args=("departure_time", f"dep_d_{gid}", f"dep_t_{gid}", gid))
                    c_dep2.time_input("Departure Time", value=None, key=f"dep_t_{gid}", on_change=db_update_datetime, args=("departure_time", f"dep_d_{gid}", f"dep_t_{gid}", gid))
            else:
                dep_d, dep_t = parse_dt(dep_val)
                c_dep1, c_dep2 = st.columns(2)
                c_dep1.date_input("Departure Date", value=dep_d, format="DD/MM/YYYY", key=f"dep_d_{gid}", on_change=db_update_datetime, args=("departure_time", f"dep_d_{gid}", f"dep_t_{gid}", gid))
                c_dep2.time_input("Departure Time", value=dep_t, key=f"dep_t_{gid}", on_change=db_update_datetime, args=("departure_time", f"dep_d_{gid}", f"dep_t_{gid}", gid))

        with col_l2:
            st.markdown("#### 🏨 Room Allocation")
            st.text_input("Housing / Room", value=guest_data.get('housing', 'TBD'), key=f"hou_{gid}", on_change=db_update, args=("housing", f"hou_{gid}", gid))

    with t_team:
        col_t1, col_t2 = st.columns(2)
        with col_t1:
            st.text_input("POC Name", value=guest_data.get('poc', ''), key=f"poc_{gid}", on_change=db_update, args=("poc", f"poc_{gid}", gid))
            
            gre_df = conn.query("SELECT gre_name FROM gres", ttl=0)
            avail_gres = ["-- Unassigned --"] + gre_df['gre_name'].tolist() if not gre_df.empty else ["-- Unassigned --"]
            current_gre = guest_data.get('assigned_gre') if pd.notna(guest_data.get('assigned_gre')) and str(guest_data.get('assigned_gre')).strip() not in ["", "None"] else "-- Unassigned --"
            if current_gre not in avail_gres: avail_gres.append(current_gre)
            
            st.selectbox("Assigned GRE", avail_gres, index=avail_gres.index(current_gre), key=f"gre_{gid}", on_change=update_gre_cb, args=(f"gre_{gid}", gid))
            st.info(f"**Admin Owner:** {guest_data.get('admin_owner', 'System')}")

        with col_t2:
            st.markdown("#### 🏨 Housing Support")
            st.markdown("📞 **Call Housing:** [9699372475](tel:9699372475)")
            st.divider()
            
            if current_gre != "-- Unassigned --":
                gre_query = conn.query("SELECT gre_phone FROM gres WHERE gre_name = :n", params={"n": current_gre}, ttl=0)
                if not gre_query.empty:
                    raw_phone = str(gre_query.iloc[0]['gre_phone']).strip()
                    if raw_phone and raw_phone.lower() not in ["none", "nan", ""]:
                        st.markdown(f"📞 **Call {current_gre}:** [{raw_phone}](tel:{raw_phone})")
                        clean_phone = re.sub(r'\D', '', raw_phone) 
                        arr_str = format_for_wa(guest_data.get('arrival_time'))
                        dep_str = format_for_wa(guest_data.get('departure_time'))
                        room_str = guest_data.get('housing', 'TBD')
                        poc_str = guest_data.get('poc', 'TBD')
                        pax_str = guest_data.get('accompanying_persons', 0)
                        gift_str = guest_data.get('gift_type', 'Pending')
                        ash_str = "Yes" if guest_data.get('ashram_tour') else "No"
                        
                        wa_msg = f"🛎️ *New VIP Assignment*\n\nHello {current_gre},\nYou have been assigned as the GRE for the following guest:\n\n👤 *Guest:* {guest_data['name']} (+{pax_str} Pax)\n✈️ *Arrival:* {arr_str}\n🛫 *Departure:* {dep_str}\n🏨 *Room Allotment:* {room_str}\n📞 *Guest POC:* {poc_str}\n🎁 *Gift Status:* {gift_str}\n🛕 *Ashram Tour:* {ash_str}"
                        if clean_remarks.strip(): wa_msg += f"\n\n📝 *Notes:*\n{clean_remarks.strip()}"
                        wa_msg += "\n\nPlease ensure everything is ready."
                        
                        wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}"
                        st.link_button("💬 Send WhatsApp Itinerary", wa_url, use_container_width=True)
                    else:
                        st.warning(f"⚠️ No phone number saved for {current_gre}.")
                else:
                    st.warning(f"⚠️ GRE '{current_gre}' not found in the GRE database.")

        st.divider()
        col_r1, col_r2 = st.columns([1, 1])
        with col_r1:
            st.markdown("#### 📝 Primary Remarks")
            st.text_area("Main instructions or alerts for the team.", value=clean_remarks, key=f"rem_{gid}", on_change=db_update, args=("remarks", f"rem_{gid}", gid), height=150)
            st.checkbox("📌 Pin to Profile Header", value=is_pinned, key=f"pin_{gid}", on_change=toggle_pin_cb, args=(f"pin_{gid}", gid))
            
        with col_r2:
            st.markdown("#### 💬 Audit Log & Updates")
            notes_df = conn.query("SELECT admin_name, note_text, timestamp FROM guest_notes WHERE guest_id = :gid ORDER BY timestamp ASC", params={"gid": gid}, ttl=0)
            chat_container = st.container(height=150)
            with chat_container:
                if notes_df.empty: st.caption("No timeline updates yet.")
                else:
                    for _, row in notes_df.iterrows():
                        dt_str = row['timestamp'].strftime('%d %b, %H:%M') if pd.notna(row['timestamp']) else ''
                        st.markdown(f"<span style='font-size: 13px;'>**{row['admin_name']}** <span style='color: #888;'>({dt_str})</span><br>{row['note_text']}</span><hr style='margin: 6px 0; border-color: #eee;'>", unsafe_allow_html=True)
            current_admin = st.session_state.get('user', 'System')
            st.text_input("Add quick update to log...", key=f"new_note_{gid}", on_change=add_guest_note_cb, args=(f"new_note_{gid}", gid, current_admin))

@st.dialog("🛠️ Batch Actions", width="medium")
def batch_actions_dialog(selected_ids):
    st.write(f"**Applying changes to {len(selected_ids)} selected guests.**")
    gre_df = conn.query("SELECT gre_name FROM gres", ttl=0)
    avail_gres = ["-- No Change --"] + gre_df['gre_name'].tolist() if not gre_df.empty else ["-- No Change --"]
    
    batch_gre = st.selectbox("Assign GRE", avail_gres)
    batch_room = st.selectbox("Update Room", ["-- No Change --", "Mark Cleaned", "Mark Dirty/Pending"])
    batch_pickup = st.selectbox("Update Pickup", ["-- No Change --", "Mark Sent", "Mark Pending"])

    if st.button("Apply Changes", type="primary", use_container_width=True):
        with conn.session as s:
            for gid in selected_ids:
                if batch_gre != "-- No Change --": s.execute(text("UPDATE guests SET assigned_gre = :g WHERE id = :id"), {"g": batch_gre, "id": gid})
                if batch_room != "-- No Change --":
                    r_val = 1 if batch_room == "Mark Cleaned" else 0
                    s.execute(text("UPDATE guests SET room_cleaned = :r WHERE id = :id"), {"r": r_val, "id": gid})
                if batch_pickup != "-- No Change --":
                    p_val = 1 if batch_pickup == "Mark Sent" else 0
                    s.execute(text("UPDATE guests SET airport_pickup_sent = :p WHERE id = :id"), {"p": p_val, "id": gid})
            s.commit()
        st.success(f"Updated {len(selected_ids)} guests!")
        for gid in selected_ids: st.session_state[f"chk_{gid}"] = False
        st.rerun()
