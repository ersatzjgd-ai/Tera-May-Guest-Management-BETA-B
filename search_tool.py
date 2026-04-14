import streamlit as st
import pandas as pd
import urllib.parse
import re
from database import conn
from ddp_modal import ddp_dialog, batch_actions_dialog

@st.cache_data(ttl=20)
def fetch_all_guests():
    return conn.query("SELECT * FROM guests", ttl=0)

@st.dialog("🚨 Guest Alerts Overview", width="large")
def alerts_overview_dialog(alerts_df):
    if alerts_df.empty:
        st.success("✅ All clear! No active alerts for the current search results.")
        return
        
    st.error(f"Found {len(alerts_df)} guests requiring attention.")
    
    # Display the standard table, hiding the internal GRE column to keep it clean
    display_df = alerts_df[['Guest', 'Alert(s)', 'POC']].copy()
    st.dataframe(display_df, use_container_width=True, hide_index=True)

    # --- THE NEW WHATSAPP GRE BROADCASTER ---
    st.divider()
    st.markdown("#### 💬 Notify GREs via WhatsApp")
    
    # Extract all unique individual alerts present in the current dataframe
    all_possible_alerts = set()
    for alert_str in alerts_df['Alert(s)']:
        all_possible_alerts.update(alert_str.split(" | "))
    
    # Filter out "GRE Not Assigned" since we can't message a non-existent GRE
    all_possible_alerts.discard("GRE Not Assigned")
    
    if not all_possible_alerts:
        st.info("There are no actionable alerts assigned to specific GREs right now.")
        return

    # MASTER SEQUENCE: Forces consistent order no matter the set randomization
    MASTER_ALERT_ORDER = [
        "Missing Arrival",
        "Missing Departure",
        "Room TBD",
        "Room Not Cleaned",
        "Pickup Pending",
        "Gift Pending"
    ]
    
    # Sort for consistent UI
    sorted_alerts = sorted(list(all_possible_alerts), key=lambda x: MASTER_ALERT_ORDER.index(x) if x in MASTER_ALERT_ORDER else 99)
    
    st.write("Select which alerts you want to broadcast to the assigned GREs:")
    selected_alert_types = st.multiselect(
        "Filter Alerts:",
        options=sorted_alerts,
        default=sorted_alerts,
        label_visibility="collapsed"
    )
    
    if not selected_alert_types:
        st.warning("⚠️ Please select at least one alert type to generate messages.")
        return
    
    # FIX 1: Strict NaN filtering. Drops literal strings, empty strings, and pandas <NA> objects.
    valid_gres_df = alerts_df.copy()
    valid_gres_df['GRE'] = valid_gres_df['GRE'].astype(str).str.strip()
    valid_gres_df = valid_gres_df[~valid_gres_df['GRE'].str.lower().isin(["", "nan", "none", "-- unassigned --", "<na>"])]
    
    if valid_gres_df.empty:
        st.info("All current alerts belong to guests without a GRE. Assign a GRE first to notify them.")
        return

    # FIX 2: Normalized GRE Phone Map (Whitespace and Case Insensitive for Veena)
    gre_df = conn.query("SELECT gre_name, gre_phone FROM gres", ttl=0)
    gre_phone_map = {}
    if not gre_df.empty:
        for _, r in gre_df.iterrows():
            clean_name = str(r['gre_name']).strip().lower()
            gre_phone_map[clean_name] = str(r['gre_phone'])

    # SUGGESTION A: Emoji Mapping System
    ALERT_EMOJIS = {
        "Missing Arrival": "🛬 Missing Arrival",
        "Missing Departure": "🛫 Missing Departure",
        "Room TBD": "🏨 Room TBD",
        "Room Not Cleaned": "🧹 Room Not Cleaned",
        "Pickup Pending": "🚗 Pickup Pending",
        "Gift Pending": "🎁 Gift Pending"
    }

    # Build the UI list of GREs to notify
    for gre, group in valid_gres_df.groupby('GRE'):
        gre_msg_lines = []
        
        for _, row in group.iterrows():
            # Filter and FIX 3: Enforce chronological Master Order on the guest's alerts
            raw_guest_alerts = [a for a in row['Alert(s)'].split(" | ") if a in selected_alert_types]
            sorted_guest_alerts = sorted(raw_guest_alerts, key=lambda x: MASTER_ALERT_ORDER.index(x) if x in MASTER_ALERT_ORDER else 99)
            
            if sorted_guest_alerts:
                # Apply Emojis to the final list
                emojified_alerts = [ALERT_EMOJIS.get(a, a) for a in sorted_guest_alerts]
                gre_msg_lines.append(f"👤 *{row['Guest']}:* {' | '.join(emojified_alerts)}")
        
        # If the GRE has actionable items after filtering, show their button
        if gre_msg_lines:
            # Match against the normalized map (prevents " Veena" from failing)
            raw_phone = gre_phone_map.get(gre.lower(), "")
            clean_phone = re.sub(r'\D', '', str(raw_phone))
            
            wa_msg = f"🚨 *Action Required - VIP Guest Alerts*\n\nHello {gre},\nPlease address the following pending items for your assigned guests:\n\n"
            wa_msg += "\n".join(gre_msg_lines)
            
            with st.container(border=True):
                col1, col2 = st.columns([3, 1])
                with col1:
                    st.markdown(f"**{gre}**")
                    st.caption(f"{len(gre_msg_lines)} guests need attention based on your filters.")
                with col2:
                    if clean_phone:
                        wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}"
                        st.link_button("💬 Send Alert Digest", wa_url, use_container_width=True)
                    else:
                        st.error("No Phone # saved")


@st.fragment
def search_results_fragment():
    raw_df = fetch_all_guests()
    
    # Expanded Defensive Column Check to include all alert triggers
    expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 
                'arrival_time', 'departure_time', 'housing', 'gift_type', 'ashram_tour', 
                'room_cleaned', 'airport_pickup_sent']
    for col in expected:
        if col not in raw_df.columns: raw_df[col] = None 
    
    if not raw_df.empty:
        raw_df['arrival_dt'] = pd.to_datetime(raw_df['arrival_time'], format='%d/%m/%Y %H:%M', errors='coerce')
        raw_df = raw_df.sort_values(by=['arrival_dt', 'name'], ascending=[True, True], na_position='last')
        raw_df['category'] = raw_df['category'].apply(lambda x: str(x).strip().title() if pd.notna(x) and str(x).strip() else None)

    st.markdown("## **🔍 Guest Management System**")
    
    all_guests = sorted([str(x) for x in raw_df['name'].dropna().unique() if str(x).strip()])
    all_pocs = sorted([str(x) for x in raw_df['poc'].dropna().unique() if str(x).strip()])
    available_cats = sorted(list(set([str(x) for x in raw_df['category'].dropna() if str(x).strip()])))
    
    with st.container(border=True):
        st.markdown("<span class='search-box-target'></span>", unsafe_allow_html=True)
        col_name, col_poc = st.columns([3, 2])
        with col_name: s_name = st.selectbox("**👤 Guest Name**", options=all_guests, index=None, placeholder="Type a name...", key="s_name_input")
        with col_poc: s_poc = st.multiselect("**📞 Filter by POC**", options=all_pocs, placeholder="Select POCs...", key="s_poc_input")
        
        col_cat, col_date, col_unassigned = st.columns([3, 2, 2])
        with col_cat: s_cat = st.multiselect("**🏷️ Category**", options=available_cats, placeholder="Select categories...")
        with col_date: s_date = st.date_input("**📅 Arrival Date Range**", value=[])
        with col_unassigned:
            st.markdown("<div style='height: 32px;'></div>", unsafe_allow_html=True)
            s_unassigned = st.checkbox("**🚨 Show ONLY Unassigned GRE**")

    filtered_df = raw_df.copy()
    if s_name: filtered_df = filtered_df[filtered_df['name'] == s_name]
    if s_poc: filtered_df = filtered_df[filtered_df['poc'].isin(s_poc)]
    if s_cat: filtered_df = filtered_df[filtered_df['category'].isin(s_cat)]
    if len(s_date) == 2: filtered_df = filtered_df[(filtered_df['arrival_dt'].dt.date >= s_date[0]) & (filtered_df['arrival_dt'].dt.date <= s_date[1])]
    elif len(s_date) == 1: filtered_df = filtered_df[filtered_df['arrival_dt'].dt.date == s_date[0]]
    if s_unassigned: filtered_df = filtered_df[filtered_df['assigned_gre'].isna() | filtered_df['assigned_gre'].str.strip().isin(["", "-- Unassigned --", "None"])]

    # --- THE UPGRADED ALERTS ENGINE ---
    alerts_list = []
    if not filtered_df.empty:
        for _, row in filtered_df.iterrows():
            guest_alerts = []
            
            # 1. GRE Missing
            if pd.isna(row.get('assigned_gre')) or str(row.get('assigned_gre')).strip() in ["", "-- Unassigned --", "None"]:
                guest_alerts.append("GRE Not Assigned")
                
            # 2. Arrival Date Missing
            arr_val = row.get('arrival_time')
            if pd.isna(arr_val) or str(arr_val).strip() in ["", "TBD", "None", "nan", "NaT"]:
                guest_alerts.append("Missing Arrival")
                
            # 3. Departure Date Missing
            dep_val = row.get('departure_time')
            if pd.isna(dep_val) or str(dep_val).strip() in ["", "TBD", "None", "nan", "NaT"]:
                guest_alerts.append("Missing Departure")
                
            # 4. Room Allocation & Cleaning Status
            housing = str(row.get('housing', 'TBD')).strip().upper()
            if housing in ["", "TBD", "NONE", "NAN"]:
                guest_alerts.append("Room TBD")
            elif not bool(row.get('room_cleaned', 0)):
                guest_alerts.append("Room Not Cleaned")
                
            # 5. Airport Pickup Status
            if not bool(row.get('airport_pickup_sent', 0)):
                guest_alerts.append("Pickup Pending")
                
            # 6. Gift Status
            gift = str(row.get('gift_type', 'Pending')).strip().title()
            if gift in ["", "Pending", "None", "Nan"]:
                guest_alerts.append("Gift Pending")

            if guest_alerts: 
                # Included the GRE in the hidden dataframe so the Modal can group them later
                alerts_list.append({
                    "Guest": row['name'], 
                    "Alert(s)": " | ".join(guest_alerts), 
                    "POC": row['poc'],
                    "GRE": str(row.get('assigned_gre')).strip()
                })
    
    alerts_df = pd.DataFrame(alerts_list)
    num_alerts = len(alerts_df)

    st.markdown("""
        <style>
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-box-target) { background-color: #FFF9C4 !important; border: 2px solid #FBC02D !important; }
        div[data-testid="stVerticalBlockBorderWrapper"]:has(.search-box-target) > div { background-color: #FFF9C4 !important; }
        div.element-container:has(.btn-red-target) + div.element-container button { background-color: #ff4b4b !important; color: white !important; border: none !important; }
        div.element-container:has(.btn-green-target) + div.element-container button { background-color: #04AA6D !important; color: white !important; border: none !important; }
        </style>
    """, unsafe_allow_html=True)

    st.markdown("<div id='results-anchor'></div>", unsafe_allow_html=True)
    if s_name or s_poc or s_cat or s_date or s_unassigned:
        st.markdown("<iframe src=\"javascript:window.parent.document.getElementById('results-anchor').scrollIntoView({behavior: 'smooth'});\" width='0' height='0' style='border:none; display:none;'></iframe>", unsafe_allow_html=True)

    if not filtered_df.empty:
        total = len(filtered_df)
        pending = len(filtered_df[filtered_df['assigned_gre'].isna() | filtered_df['assigned_gre'].str.strip().isin(["", "-- Unassigned --", "None"])])
        cat_counts = filtered_df['category'].value_counts()
        cat_html = "".join([f"<span style='margin-right: 25px;'><b>🏷️ {k}:</b> {v}</span>" for k, v in cat_counts.items()])

        st.markdown(f"<div style='background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin: 10px 0px;'><span style='margin-right: 25px;'><b>Total:</b> {total}</span><span style='margin-right: 25px;'><b>🚨 Pending GRE:</b> {pending}</span>{cat_html}</div>", unsafe_allow_html=True)

        display_df = filtered_df.copy()
        display_df['assigned_gre'] = display_df['assigned_gre'].apply(lambda x: "🚨 Pending" if pd.isna(x) or str(x).strip() in ["", "-- Unassigned --", "None"] else x)
        
        if len(display_df) > 20:
            ui_df = display_df[['name', 'arrival_time', 'poc', 'assigned_gre', 'accompanying_persons']].copy()
            ui_df.columns = ['Guest', 'Arrival', 'POC', 'GRE', '+1s']
            col_table, col_actions = st.columns([12, 2])
            with col_table:
                event = st.dataframe(ui_df, use_container_width=True, hide_index=True, selection_mode="multi-row", on_select="rerun")
            with col_actions:
                if num_alerts > 0:
                    st.markdown("<span class='btn-red-target'></span>", unsafe_allow_html=True)
                    if st.button(f"🔴 ALERTS ({num_alerts})", use_container_width=True): alerts_overview_dialog(alerts_df)
                else:
                    st.markdown("<span class='btn-green-target'></span>", unsafe_allow_html=True)
                    if st.button("🟢 ALERTS (0)", use_container_width=True): alerts_overview_dialog(alerts_df)
                st.divider()
                selected_indices = event.selection.rows
                if selected_indices:
                    st.markdown("### ⚡ Actions")
                    selected_ids = [filtered_df.iloc[i]['id'] for i in selected_indices]
                    if len(selected_ids) == 1:
                        if st.button("📂 Open Guest Details", type="primary", use_container_width=True): ddp_dialog(filtered_df[filtered_df['id'] == selected_ids[0]].iloc[0].to_dict())
                    elif len(selected_ids) > 1:
                        if st.button(f"⚙️ Apply Batch Actions ({len(selected_ids)})", type="primary", use_container_width=True): batch_actions_dialog(selected_ids)
                else:
                    st.caption("👈 Select a guest in the table to view actions.")
        else:
            col_hdr, col_alt = st.columns([10, 2])
            with col_hdr: st.markdown("### ⚡ Quick Actions")
            with col_alt:
                if num_alerts > 0:
                    st.markdown("<span class='btn-red-target'></span>", unsafe_allow_html=True)
                    if st.button(f"🔴 ALERTS ({num_alerts})", key="alt_btn_sm", use_container_width=True): alerts_overview_dialog(alerts_df)
                else:
                    st.markdown("<span class='btn-green-target'></span>", unsafe_allow_html=True)
                    if st.button("🟢 ALERTS (0)", key="alt_btn_sm", use_container_width=True): alerts_overview_dialog(alerts_df)

            for _, row in display_df.iterrows():
                with st.container(border=True):
                    c_name, c_arr, c_poc, c_acc, c_gre = st.columns([3, 2, 2, 1, 3])
                    with c_name:
                        if st.button(f" {row['name']}", key=f"btn_name_{row['id']}", use_container_width=True): ddp_dialog(row.to_dict())
                    with c_arr: st.write(f"Arrival {row['arrival_time']}")
                    with c_poc: st.write(f"POC: {row['poc']}")
                    with c_acc:
                        acc = row['accompanying_persons']
                        acc_val = int(acc) if pd.notna(acc) and str(acc).isdigit() else (acc if pd.notna(acc) else 0)
                        st.write(f"Extras +{acc_val}")
                    with c_gre:
                        if "🚨 Pending" in str(row['assigned_gre']): st.markdown(":red[**🚨 GRE NOT ASSIGNED**]")
                        else: st.write(f"GRE: {row['assigned_gre']}")
