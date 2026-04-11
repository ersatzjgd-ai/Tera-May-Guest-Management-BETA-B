import streamlit as st
import pandas as pd
from sqlalchemy import text
import datetime
from database import conn

# --- HELPER FUNCTION FOR MISSING DATA HIGHLIGHTS ---
def missing_alert(val, default_text="TBD"):
    """Returns the value normally, or a bold RED warning if the data is missing/TBD."""
    if pd.isna(val) or str(val).strip() in ["", "None", "--", "TBD", "Unassigned", "-- Unassigned --", "nan"]:
        return f":red[**{default_text}**]"
    return str(val).strip()

@st.dialog("DDP - Dignitary Details Page", width="large")
def ddp_dialog(guest_data):
    st.subheader(f"Dignitary: {guest_data['name']}")
    
    info_c1, info_c2, info_c3 = st.columns(3)
    
    with info_c1:
        st.markdown("### 🪪 Profile")
        st.write(f"**Category:** {missing_alert(guest_data.get('category'))}")
        st.write(f"**Speaker Status:** {missing_alert(guest_data.get('speaker_category'))}")
        pax_val = int(guest_data['accompanying_persons']) if pd.notna(guest_data.get('accompanying_persons')) else 0
        st.write(f"**Accompanying Pax:** {pax_val}")
        st.write(f"**POC Name:** {missing_alert(guest_data.get('poc'))}")

    with info_c2:
        st.markdown("### ✈️ Logistics")
        st.write(f"**Housing/Room:** {missing_alert(guest_data.get('housing'))}")
        st.write(f"**Arrival:** {missing_alert(guest_data.get('arrival_time'))}")
        st.write(f"**Departure:** {missing_alert(guest_data.get('departure_time'))}")
        st.write(f"**Admin Owner:** {missing_alert(guest_data.get('admin_owner'))}")
        st.write(f"**Assigned GRE:** {missing_alert(guest_data.get('assigned_gre'), 'Unassigned')}")
    
    with info_c3:
        st.markdown("### 🛎️ Ground Status")
        room_val = bool(guest_data['room_cleaned'])
        new_room = st.toggle("Room Cleaned", value=room_val, key=f"ddp_rm_{guest_data['id']}")
        if new_room != room_val:
            with conn.session as s:
                s.execute(text("UPDATE guests SET room_cleaned = :r WHERE id = :id"), {"r": int(new_room), "id": guest_data['id']})
                s.commit()
            st.rerun()

        pickup_val = bool(guest_data['airport_pickup_sent'])
        new_pickup = st.toggle("Pickup Sent", value=pickup_val, key=f"ddp_pk_{guest_data['id']}")
        if new_pickup != pickup_val:
            with conn.session as s:
                s.execute(text("UPDATE guests SET airport_pickup_sent = :p WHERE id = :id"), {"p": int(new_pickup), "id": guest_data['id']})
                s.commit()
            st.rerun()
        
    st.divider()
    
    # --- EDIT SECTION ---
    with st.expander("📝 Edit Profile Details"):
        with st.form(f"edit_form_{guest_data['id']}"):
            e_name = st.text_input("Guest Name", value=guest_data['name'])
            e_cat = st.text_input("Category", value=guest_data['category'] if pd.notna(guest_data['category']) else "")
            
            current_spk = guest_data['speaker_category'] if pd.notna(guest_data.get('speaker_category')) else "Non-Speaker"
            e_spk = st.selectbox("Speaker Status", ["Speaker", "Non-Speaker"], index=0 if current_spk == "Speaker" else 1)
            
            e_pax = st.number_input("Accompanying Persons", min_value=0, value=pax_val)
            e_poc = st.text_input("POC Name", value=guest_data['poc'] if pd.notna(guest_data.get('poc')) else "")
            
            # Fetch available GREs
            gre_df = conn.query("SELECT gre_name FROM gres", ttl=0)
            avail_gres = ["-- Unassigned --"] + gre_df['gre_name'].tolist() if not gre_df.empty else ["-- Unassigned --"]
            
            current_gre = guest_data['assigned_gre'] if pd.notna(guest_data.get('assigned_gre')) and str(guest_data['assigned_gre']).strip() not in ["", "None"] else "-- Unassigned --"
            if current_gre not in avail_gres:
                avail_gres.append(current_gre)
                
            e_gre = st.selectbox("Assign GRE", avail_gres, index=avail_gres.index(current_gre))
            
            st.divider()
            st.write("**✈️ Logistics Update**")
            
            # New Housing Input
            current_hou = guest_data['housing'] if pd.notna(guest_data.get('housing')) and str(guest_data['housing']).strip() != "" else "TBD"
            e_hou = st.text_input("Housing / Room Allotment", value=current_hou)
            
            def parse_dt(dt_str):
                if not dt_str or pd.isna(dt_str) or str(dt_str).strip() in ["", "TBD"]:
                    return datetime.date.today(), datetime.time(12, 0)
                try:
                    dt_obj = datetime.datetime.strptime(str(dt_str).strip(), "%d/%m/%Y %H:%M")
                    return dt_obj.date(), dt_obj.time()
                except:
                    return datetime.date.today(), datetime.time(12, 0)

            arr_d, arr_t = parse_dt(guest_data.get('arrival_time'))
            dep_d, dep_t = parse_dt(guest_data.get('departure_time'))

            c1, c2 = st.columns(2)
            with c1:
                st.markdown("**Arrival**")
                new_arr_d = st.date_input("Arrival Date (DD/MM)", value=arr_d, format="DD/MM/YYYY")
                new_arr_t = st.time_input("Arrival Time", value=arr_t)
            with c2:
                st.markdown("**Departure**")
                new_dep_d = st.date_input("Departure Date (DD/MM)", value=dep_d, format="DD/MM/YYYY")
                new_dep_t = st.time_input("Departure Time", value=dep_t)
            
            if st.form_submit_button("Save Changes"):
                final_gre = None if e_gre == "-- Unassigned --" else e_gre
                
                final_arr = f"{new_arr_d.strftime('%d/%m/%Y')} {new_arr_t.strftime('%H:%M')}"
                final_dep = f"{new_dep_d.strftime('%d/%m/%Y')} {new_dep_t.strftime('%H:%M')}"
                
                with conn.session as s:
                    s.execute(text("""
                        UPDATE guests SET 
                        name = :n, category = :cat, speaker_category = :spk, 
                        accompanying_persons = :pax, poc = :poc, arrival_time = :arr, 
                        departure_time = :dep, assigned_gre = :gre, housing = :hou
                        WHERE id = :id
                    """), {
                        "n": e_name, "cat": e_cat, "spk": e_spk, "pax": e_pax, 
                        "poc": e_poc, "arr": final_arr, "dep": final_dep, "gre": final_gre, "hou": e_hou, "id": int(guest_data['id'])
                    })
                    s.commit()
                st.success("Information updated!")
                st.rerun()

# --- BATCH ACTIONS DIALOG ---
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
                if batch_gre != "-- No Change --":
                    s.execute(text("UPDATE guests SET assigned_gre = :g WHERE id = :id"), {"g": batch_gre, "id": gid})
                if batch_room != "-- No Change --":
                    r_val = 1 if batch_room == "Mark Cleaned" else 0
                    s.execute(text("UPDATE guests SET room_cleaned = :r WHERE id = :id"), {"r": r_val, "id": gid})
                if batch_pickup != "-- No Change --":
                    p_val = 1 if batch_pickup == "Mark Sent" else 0
                    s.execute(text("UPDATE guests SET airport_pickup_sent = :p WHERE id = :id"), {"p": p_val, "id": gid})
            s.commit()
        st.success(f"Updated {len(selected_ids)} guests!")
        
        for gid in selected_ids:
            st.session_state[f"chk_{gid}"] = False
        st.rerun()
