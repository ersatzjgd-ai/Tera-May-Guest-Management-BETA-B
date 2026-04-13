import streamlit as st
import pandas as pd
from sqlalchemy import text
import extra_streamlit_components as stx
import datetime
from database import conn, init_db
from ui_components import ddp_dialog, batch_actions_dialog

# --- 1. DATA CACHING (The Speed Secret) ---
@st.cache_data(ttl=20)
def fetch_all_guests():
    """Fetches data and caches it for 20 seconds to prevent DB latency"""
    return conn.query("SELECT * FROM guests", ttl=0)

# --- 2. SEARCH & RESULTS FRAGMENT ---
# --- 2. SEARCH & RESULTS FRAGMENT ---
@st.fragment
def search_results_fragment():
    raw_df = fetch_all_guests()
    
    # Defensive Column Check
    expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 'departure_time', 'housing', 'gift_type', 'ashram_tour']
    for col in expected:
        if col not in raw_df.columns: raw_df[col] = None 
    
    if not raw_df.empty:
        raw_df['arrival_dt'] = pd.to_datetime(raw_df['arrival_time'], format='%d/%m/%Y %H:%M', errors='coerce')
        raw_df = raw_df.sort_values(by=['arrival_dt', 'name'], ascending=[True, True], na_position='last')

    # --- 1. HERO SEARCH SECTION ---
    st.markdown("### 🔍 Search Directory")
    
    all_guests = sorted([str(x) for x in raw_df['name'].dropna().unique() if str(x).strip()])
    all_pocs = sorted([str(x) for x in raw_df['poc'].dropna().unique() if str(x).strip()])
    
    # Making the Search Box more prominent (Larger Column)
    col_search, col_poc = st.columns([4, 2])
    with col_search: 
        s_name = st.selectbox("👤 QUICK FIND: START TYPING GUEST NAME", options=all_guests, index=None, placeholder="Search from 4000+ records...", key="s_name_input")
    with col_poc: 
        s_poc = st.multiselect("📞 Filter by POC", options=all_pocs, placeholder="All POCs", key="s_poc_input")
    
    # Tucking away the "Maintenance" filters
    s_cat, s_date = [], []
    with st.expander("🛠️ More Search Filters (Category, Date Range)"):
        f_cat, f_date = st.columns(2)
        with f_cat:
            available = sorted(list(set([str(x) for x in raw_df['category'].dropna() if str(x).strip()])))
            s_cat = st.multiselect("🏷️ Category", options=available)
        with f_date: 
            s_date = st.date_input("📅 Arrival Range", value=[])

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

    # --- 2. COMPACT SUMMARY BAR (Smaller Metrics) ---
    if not filtered_df.empty:
        total = len(filtered_df)
        speakers = len(filtered_df[filtered_df['speaker_category'] == 'Speaker'])
        pending = len(filtered_df[filtered_df['assigned_gre'].isna() | filtered_df['assigned_gre'].str.strip().isin(["", "-- Unassigned --", "None"])])

        # Using a styled markdown container for a "Summary Bar" look
        st.markdown(f"""
            <div style="background-color: #f0f2f6; padding: 10px; border-radius: 10px; margin: 10px 0px;">
                <span style="margin-right: 25px;"><b>Total:</b> {total}</span>
                <span style="margin-right: 25px;"><b>🎙️ Speakers:</b> {speakers}</span>
                <span><b>🚨 Pending GRE:</b> {pending}</span>
            </div>
        """, unsafe_allow_allowed=True)

        # --- 3. DATA GRID ---
        display_df = filtered_df.copy()
        display_df['assigned_gre'] = display_df['assigned_gre'].apply(
            lambda x: "🚨 Pending" if pd.isna(x) or str(x).strip() in ["", "-- Unassigned --", "None"] else x
        )
        
        ui_df = display_df[['name', 'arrival_time', 'poc', 'assigned_gre', 'accompanying_persons']].copy()
        ui_df.columns = ['Guest', 'Arrival', 'POC', 'GRE', '+1s']
        
        event = st.dataframe(
            ui_df,
            use_container_width=True,
            hide_index=True,
            selection_mode="multi-row",
            on_select="rerun"
        )
        
        # Action Buttons
        selected_indices = event.selection.rows
        if selected_indices:
            selected_ids = [filtered_df.iloc[i]['id'] for i in selected_indices]
            if len(selected_ids) == 1:
                if st.button("📂 Open Guest Details", type="primary", use_container_width=True):
                    guest_data = filtered_df[filtered_df['id'] == selected_ids[0]].iloc[0].to_dict()
                    ddp_dialog(guest_data)
            elif len(selected_ids) > 1:
                if st.button(f"⚙️ Apply Batch Actions ({len(selected_ids)})", type="primary", use_container_width=True):
                    batch_actions_dialog(selected_ids)


# --- 3. ADMIN TOOLS FRAGMENT ---
@st.fragment
def admin_tools_fragment():
    with st.expander("🛠️ Admin Tools (Add GRE / Bulk Import)"):
        t1, t2 = st.tabs(["Add GRE", "CSV Import"])
        
        with t1:
            with st.form("gre_f", clear_on_submit=True):
                gn = st.text_input("Name")
                gp = st.text_input("Phone (e.g., 9876543210)")
                if st.form_submit_button("Create GRE"):
                    clean_phone = "".join(c for c in str(gp) if c.isdigit() or c == "+")
                    if clean_phone and not clean_phone.startswith("+"): clean_phone = "+91" + clean_phone
                    with conn.session as s:
                        s.execute(text("INSERT INTO gres (gre_name, gre_phone) VALUES (:n, :p)"), {"n": gn, "p": clean_phone})
                        s.commit()
                    st.cache_data.clear()
                    st.success(f"Added {gn}!")

        with t2:
            st.info("📄 **CSV Required Columns:** `name`, `admin_username` (Optional: `poc`, `category`, `housing`, etc.)")
            f = st.file_uploader("Upload CSV", type="csv", key="bulk_csv_uploader")
            if f and st.button("Run Import", type="primary", key="csv_import_btn"):
                data = pd.read_csv(f)
                data.columns = data.columns.str.lower().str.strip()
                with conn.session as s:
                    for _, r in data.iterrows():
                        g_name, a_user = str(r['name']).strip(), str(r['admin_username']).strip()
                        s.execute(text("INSERT INTO admins (username, password) VALUES (:u, :p) ON CONFLICT DO NOTHING"), {"u": a_user, "p": "password123"})
                        
                        # Data Mapping
                        cat = str(r.get('category', '')).strip()
                        hou = str(r.get('housing', 'TBD')).strip()
                        spk = str(r.get('speaker_category', 'Non-Speaker')).strip()
                        
                        existing = s.execute(text("SELECT id FROM guests WHERE name = :n AND admin_owner = :u"), {"n": g_name, "u": a_user}).fetchone()
                        if existing:
                            s.execute(text("UPDATE guests SET category=:c, housing=:h, speaker_category=:s WHERE id=:id"), {"c":cat, "h":hou, "s":spk, "id":existing[0]})
                        else:
                            s.execute(text("INSERT INTO guests (name, admin_owner, category, housing, speaker_category) VALUES (:n, :u, :c, :h, :s)"), {"n":g_name, "u":a_user, "c":cat, "h":hou, "s":spk})
                    s.commit()
                st.cache_data.clear()
                st.success("Import Finished!")

# --- MAIN APP FLOW ---
def main():
    st.set_page_config(page_title="Dignitary Management", layout="wide")
    init_db()

    if "logged_in" not in st.session_state: st.session_state.logged_in = False

    st.sidebar.title("🛂 Event Control")
    mode = st.sidebar.radio("Navigate to:", ["Public Search", "Staff Portal (GRE)", "Admin Portal"])

    if mode == "Public Search":
        st.title("🛂 Guest Inquiry")
        search = st.text_input("Enter Guest Name")
        if search:
            df = conn.query("SELECT name, arrival_time, departure_time, housing FROM guests WHERE name ILIKE :n", params={"n": f"%{search}%"}, ttl=0)
            st.dataframe(df, use_container_width=True)

    elif mode == "Staff Portal (GRE)":
        st.title("🛎️ GRE Portal)")
        gre_name = st.text_input("Enter GRE Name")
        if gre_name:
            st.info(f"Welcome {gre_name}. (Feature logic remains in main script for now).")

    elif mode == "Admin Portal":
        # Login logic
        if not st.session_state.logged_in:
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.button("Login"):
                res = conn.query("SELECT * FROM admins WHERE username = :u AND password = :p", params={"u": u, "p": p}, ttl=0)
                if not res.empty:
                    st.session_state.logged_in, st.session_state.user = True, u
                    st.rerun()
        
        if st.session_state.logged_in:
            search_results_fragment()
            st.divider()
            admin_tools_fragment()

if __name__ == "__main__":
    main()
