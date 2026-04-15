import streamlit as st
import pandas as pd
import urllib.parse
import re
import datetime
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

    # Fetch GRE phones for the WhatsApp logic
    gre_data = conn.query("SELECT gre_name, gre_phone FROM gres", ttl=0)
    gre_phone_map = {}
    if not gre_data.empty:
        for _, r in gre_data.iterrows():
            clean_name = str(r['gre_name']).strip().lower()
            gre_phone_map[clean_name] = str(r['gre_phone'])

    # MASTER SEQUENCE & EMOJIS
    MASTER_ALERT_ORDER = ["Missing Arrival", "Missing Departure", "Room TBD", "Room Not Cleaned", "Pickup Pending", "Gift Pending"]
    ALERT_EMOJIS = {
        "Missing Arrival": "🛬 Missing Arrival", "Missing Departure": "🛫 Missing Departure",
        "Room TBD": "🏨 Room TBD", "Room Not Cleaned": "🧹 Room Not Cleaned",
        "Pickup Pending": "🚗 Pickup Pending", "Gift Pending": "🎁 Gift Pending"
    }

    tab_individual, tab_group = st.tabs(["👤 Guest Action Center", "📊 GRE Digest (Bulk)"])

    with tab_individual:
        st.markdown("##### Immediate updates for individual guests")
        # Ensure we have a clean GRE column for filtering
        valid_indiv = alerts_df.copy()
        valid_indiv['GRE_clean'] = valid_indiv['GRE'].astype(str).str.strip().str.lower()

        # Sort by Guest Name for easy finding
        valid_indiv = valid_indiv.sort_values('Guest')

        for _, row in valid_indiv.iterrows():
            with st.container(border=True):
                c1, c2 = st.columns([3, 1])
                with c1:
                    st.markdown(f"**{row['Guest']}**")
                    # Display alerts as clear, colored tags
                    alert_items = row['Alert(s)'].split(" | ")
                    formatted_alerts = "  •  ".join([f":orange[{a}]" for a in alert_items])
                    st.markdown(formatted_alerts)
                    
                    if row['GRE_clean'] in ["", "nan", "none", "-- unassigned --"]:
                        st.caption("⚠️ :red[No GRE Assigned]")
                    else:
                        st.caption(f"Assigned GRE: **{row['GRE']}**")

                with c2:
                    raw_phone = gre_phone_map.get(row['GRE_clean'], "")
                    clean_phone = re.sub(r'\D', '', str(raw_phone))
                    if clean_phone:
                        emojified = [ALERT_EMOJIS.get(a.strip(), a.strip()) for a in alert_items]
                        indiv_msg = f"🚨 *Guest Update*\n\nHello {row['GRE']},\nRegarding guest *{row['Guest']}*, please check:\n\n" + "\n".join([f"- {e}" for e in emojified])
                        wa_url = f"https://wa.me/{clean_phone}?text={urllib.parse.quote(indiv_msg)}"
                        st.link_button("💬 Send Alert on Whatsapp", wa_url, use_container_width=True)
                    else:
                        st.button("🚫 No Phone", disabled=True, use_container_width=True)

    with tab_group:
        st.markdown("##### Notify GREs of all their assigned alerts")
        all_possible_alerts = set()
        for alert_str in alerts_df['Alert(s)']:
            all_possible_alerts.update(alert_str.split(" | "))
        all_possible_alerts.discard("GRE Not Assigned")
        
        if not all_possible_alerts:
            st.info("No actionable alerts for assigned GREs.")
        else:
            sorted_alerts = sorted(list(all_possible_alerts), key=lambda x: MASTER_ALERT_ORDER.index(x) if x in MASTER_ALERT_ORDER else 99)
            selected_alert_types = st.multiselect("Filter Alerts for Digest:", options=sorted_alerts, default=sorted_alerts)
            
            valid_gres_df = alerts_df.copy()
            valid_gres_df['GRE_clean'] = valid_gres_df['GRE'].astype(str).str.strip().str.lower()
            valid_gres_df = valid_gres_df[~valid_gres_df['GRE_clean'].isin(["", "nan", "none", "-- unassigned --"])]

            for gre_name, group in valid_gres_df.groupby('GRE'):
                gre_msg_lines = []
                for _, row in group.iterrows():
                    raw_guest_alerts = [a for a in row['Alert(s)'].split(" | ") if a in selected_alert_types]
                    if raw_guest_alerts:
                        emojified = [ALERT_EMOJIS.get(a, a) for a in sorted(raw_guest_alerts, key=lambda x: MASTER_ALERT_ORDER.index(x) if x in MASTER_ALERT_ORDER else 99)]
                        gre_msg_lines.append(f"👤 *{row['Guest']}:* {' | '.join(emojified)}")
                
                if gre_msg_lines:
                    raw_phone = gre_phone_map.get(str(gre_name).strip().lower(), "")
                    clean_phone = re.sub(r'\D', '', str(raw_phone))
                    wa_msg = f"🚨 *Action Required - Guest Alerts*\n\nHello {gre_name},\nPlease address following items for your assigned guest/s:\n\n" + "\n".join(gre_msg_lines)
                    
                    with st.container(border=True):
                        gc1, gc2 = st.columns([3, 1])
                        with gc1: st.markdown(f"**{gre_name}** ({len(gre_msg_lines)} Guests)")
                        with gc2:
                            if clean_phone:
                                st.link_button("💬 Send Alert on Whatsapp", f"https://wa.me/{clean_phone}?text={urllib.parse.quote(wa_msg)}", use_container_width=True)
                            else: st.error("No Phone")

@st.fragment
def search_results_fragment():
    raw_df = fetch_all_guests()
    expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 
                'arrival_time', 'departure_time', 'housing', 'gift_type', 'ashram_tour', 
                'room_cleaned', 'airport_pickup_sent']
    for col in expected:
        if col not in raw_df.columns: raw_df[col] = None 
    
    if not raw_df.empty:
        raw_df['arrival_dt'] = pd.to_datetime(raw_df['arrival_time'], format='%d/%m/%Y %H:%M', errors='coerce')
        raw_df = raw_df.sort_values(by=['arrival_dt', 'name'], ascending=[True, True], na_position='last')
        raw_df['category'] = raw_df['category'].apply(lambda x: str(x).strip().title() if pd.notna(x) and str(x).strip() else None)
   
    st.title("## **Guest Management System**")
    st.markdown("## ****")
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
            s_unassigned = st.checkbox("**🚨 Unassigned GRE**")

    filtered_df = raw_df.copy()
    filters_engaged = any([s_name, s_poc, s_cat, s_date, s_unassigned])
    
    if filters_engaged:
        if s_name: filtered_df = filtered_df[filtered_df['name'] == s_name]
        if s_poc: filtered_df = filtered_df[filtered_df['poc'].isin(s_poc)]
        if s_cat: filtered_df = filtered_df[filtered_df['category'].isin(s_cat)]
        if len(s_date) == 2: filtered_df = filtered_df[(filtered_df['arrival_dt'].dt.date >= s_date[0]) & (filtered_df['arrival_dt'].dt.date <= s_date[1])]
        elif len(s_date) == 1: filtered_df = filtered_df[filtered_df['arrival_dt'].dt.date == s_date[0]]
        if s_unassigned: filtered_df = filtered_df[filtered_df['assigned_gre'].isna() | filtered_df['assigned_gre'].str.strip().isin(["", "-- Unassigned --", "None"])]
    else:
        today = datetime.date.today()
        filtered_df = filtered_df[filtered_df['arrival_dt'].dt.date == today]
        st.caption(f"📅 Guests arriving today ({today.strftime('%b %d, %Y')}). Engage any filter above to search all records.")

    alerts_list = []
    if not filtered_df.empty:
        for _, row in filtered_df.iterrows():
            guest_alerts = []
            if pd.isna(row.get('assigned_gre')) or str(row.get('assigned_gre')).strip() in ["", "-- Unassigned --", "None"]: guest_alerts.append("GRE Not Assigned")
            arr_val = row.get('arrival_time')
            if pd.isna(arr_val) or str(arr_val).strip() in ["", "TBD", "None", "nan", "NaT"]: guest_alerts.append("Missing Arrival")
            dep_val = row.get('departure_time')
            if pd.isna(dep_val) or str(dep_val).strip() in ["", "TBD", "None", "nan", "NaT"]: guest_alerts.append("Missing Departure")
            housing = str(row.get('housing', 'TBD')).strip().upper()
            if housing in ["", "TBD", "NONE", "NAN"]: guest_alerts.append("Room TBD")
            elif not bool(row.get('room_cleaned', 0)): guest_alerts.append("Room Not Cleaned")
            if not bool(row.get('airport_pickup_sent', 0)): guest_alerts.append("Pickup Pending")
            gift = str(row.get('gift_type', 'Pending')).strip().title()
            if gift in ["", "Pending", "None", "Nan"]: guest_alerts.append("Gift Pending")

            if guest_alerts: 
                alerts_list.append({"Guest": row['name'], "Alert(s)": " | ".join(guest_alerts), "GRE": str(row.get('assigned_gre')).strip()})
    
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
            with col_table: event = st.dataframe(ui_df, use_container_width=True, hide_index=True, selection_mode="multi-row", on_select="rerun")
            with col_actions:
                st.markdown("<span class='btn-red-target'></span>" if num_alerts > 0 else "<span class='btn-green-target'></span>", unsafe_allow_html=True)
                if st.button(f"{'🔴' if num_alerts > 0 else '🟢'} ALERTS ({num_alerts})", use_container_width=True): alerts_overview_dialog(alerts_df)
                st.divider()
                selected_indices = event.selection.rows
                if selected_indices:
                    selected_ids = [filtered_df.iloc[i]['id'] for i in selected_indices]
                    if len(selected_ids) == 1:
                        if st.button("📂 Open DDP", type="primary", use_container_width=True): ddp_dialog(filtered_df[filtered_df['id'] == selected_ids[0]].iloc[0].to_dict())
                    elif len(selected_ids) > 1:
                        if st.button(f"⚙️ Batch Actions ({len(selected_ids)})", type="primary", use_container_width=True): batch_actions_dialog(selected_ids)
        else:
            col_hdr, col_alt = st.columns([10, 2])
            with col_hdr: st.markdown("### ⚡ Quick Actions")
            with col_alt:
                st.markdown("<span class='btn-red-target'></span>" if num_alerts > 0 else "<span class='btn-green-target'></span>", unsafe_allow_html=True)
                if st.button(f"{'🔴' if num_alerts > 0 else '🟢'} ALERTS ({num_alerts})", key="alt_btn_sm", use_container_width=True): alerts_overview_dialog(alerts_df)

            for _, row in display_df.iterrows():
                with st.container(border=True):
                    c_name, c_arr, c_poc, c_acc, c_gre = st.columns([3, 2, 2, 1, 3])
                    with c_name:
                        if st.button(f" {row['name']}", key=f"btn_name_{row['id']}", use_container_width=True): ddp_dialog(row.to_dict())
                    with c_arr: st.write(f"Arrival {row['arrival_time']}")
                    with c_poc: st.write(f"POC: {row['poc']}")
                    with c_acc:
                        acc = row['accompanying_persons']
                        st.write(f"Extras +{int(acc) if pd.notna(acc) and str(acc).isdigit() else 0}")
                    with c_gre:
                        if "🚨 Pending" in str(row['assigned_gre']): st.markdown(":red[**🚨 GRE NOT ASSIGNED**]")
                        else: st.write(f"GRE: {row['assigned_gre']}")
