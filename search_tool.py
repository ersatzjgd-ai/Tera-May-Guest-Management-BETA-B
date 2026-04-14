import streamlit as st
import pandas as pd
from database import conn
from ddp_modal import ddp_dialog, batch_actions_dialog

@st.cache_data(ttl=20)
def fetch_all_guests():
    return conn.query("SELECT * FROM guests", ttl=0)

@st.dialog("🚨 Guest Alerts Overview")
def alerts_overview_dialog(alerts_df):
    if alerts_df.empty:
        st.success("✅ All clear! No active alerts for the current search results.")
    else:
        st.error(f"Found {len(alerts_df)} guests requiring attention.")
        st.dataframe(alerts_df, use_container_width=True, hide_index=True)

@st.fragment
def search_results_fragment():
    raw_df = fetch_all_guests()
    expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 'departure_time', 'housing', 'gift_type', 'ashram_tour']
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

    alerts_list = []
    if not filtered_df.empty:
        for _, row in filtered_df.iterrows():
            guest_alerts = []
            if pd.isna(row['assigned_gre']) or str(row['assigned_gre']).strip() in ["", "-- Unassigned --", "None"]:
                guest_alerts.append("GRE Not Assigned")
            if guest_alerts: alerts_list.append({"Guest": row['name'], "Alert(s)": " | ".join(guest_alerts), "POC": row['poc']})
    
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
