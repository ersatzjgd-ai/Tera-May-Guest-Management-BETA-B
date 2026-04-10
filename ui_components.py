import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import conn

@st.dialog("DDP - Dignitary Details Page", width="large")
def ddp_dialog(guest_data):
    st.subheader(f"Dignitary: {guest_data['name']}")
    
    info_c1, info_c2, info_c3 = st.columns(3)
    
    with info_c1:
        st.markdown("### 🪪 Profile")
        st.write(f"**Category:** {guest_data['category'] if pd.notna(guest_data['category']) else '--'}")
        st.write(f"**Speaker Status:** {guest_data['speaker_category'] if pd.notna(guest_data['speaker_category']) else '--'}")
        pax_val = int(guest_data['accompanying_persons']) if pd.notna(guest_data['accompanying_persons']) else 0
        st.write(f"**Accompanying Pax:** {pax_val}")
        st.write(f"**POC Name:** {guest_data['poc'] if pd.notna(guest_data['poc']) else '--'}")

    with info_c2:
        st.markdown("### ✈️ Logistics")
        st.write(f"**Arrival:** {guest_data['arrival_time'] if pd.notna(guest_data['arrival_time']) else 'TBD'}")
        st.write(f"**Departure:** {guest_data['departure_time'] if pd.notna(guest_data['departure_time']) else 'TBD'}")
        st.write(f"**Admin Owner:** {guest_data['admin_owner']}")
        st.write(f"**Assigned GRE:** {guest_data['assigned_gre'] if pd.notna(guest_data['assigned_gre']) else 'Unassigned'}")
    
    with info_c3:
        st.markdown("### 🛎️ Ground Status")
        # Quick Status Toggles
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
    
    # --- EDIT SECTION (Integrated to avoid Nested Dialog error) ---
    with st.expander("📝 Edit Profile Details"):
        with st.form(f"edit_form_{guest_data['id']}"):
            e_name = st.text_input("Guest Name", value=guest_data['name'])
            e_cat = st.text_input("Category", value=guest_data['category'] if pd.notna(guest_data['category']) else "")
            e_spk = st.selectbox("Speaker Status", ["Speaker", "Non-Speaker"], index=0 if guest_data['speaker_category'] == "Speaker" else 1)
            e_pax = st.number_input("Accompanying Persons", min_value=0, value=pax_val)
            e_poc = st.text_input("POC Name", value=guest_data['poc'] if pd.notna(guest_data['poc']) else "")
            
            st.write("**Logistics Update**")
            e_arr = st.text_input("Arrival (DD/MM/YYYY HH:MM)", value=guest_data['arrival_time'] if pd.notna(guest_data['arrival_time']) else "")
            e_dep = st.text_input("Departure (DD/MM/YYYY HH:MM)", value=guest_data['departure_time'] if pd.notna(guest_data['departure_time']) else "")
            
            if st.form_submit_button("Save Changes"):
                with conn.session as s:
                    s.execute(text("""
                        UPDATE guests SET 
                        name = :n, category = :cat, speaker_category = :spk, 
                        accompanying_persons = :pax, poc = :poc, arrival_time = :arr, 
                        departure_time = :dep 
                        WHERE id = :id
                    """), {
                        "n": e_name, "cat": e_cat, "spk": e_spk, "pax": e_pax, 
                        "poc": e_poc, "arr": e_arr, "dep": e_dep, "id": guest_data['id']
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
        
        # Un-check the boxes after successful update
        for gid in selected_ids:
            st.session_state[f"chk_{gid}"] = False
        st.rerun()
