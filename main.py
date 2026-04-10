import streamlit as st
import pandas as pd
from sqlalchemy import text
import extra_streamlit_components as stx
import datetime
from database import conn, init_db
from ui_components import ddp_dialog, batch_actions_dialog

def main():
    st.set_page_config(page_title="Dignitary Management System", layout="wide")
    init_db()

    if "logged_in" not in st.session_state: 
        st.session_state.logged_in = False
        st.session_state.user = ""

    st.sidebar.title("🛂 Event Control")
    mode = st.sidebar.radio("Navigate to:", ["Public Search", "Staff Portal (GRE)", "Admin Portal"])

    # --- 1. PUBLIC SEARCH ---
    if mode == "Public Search":
        st.title("🛂 Guest Inquiry")
        search = st.text_input("Enter Guest Name")
        if search:
            df = conn.query("SELECT name, arrival_time, departure_time, stay_location, airport_pickup_sent, room_cleaned FROM guests WHERE name ILIKE :n", params={"n": f"%{search}%"}, ttl=0)
            if not df.empty: st.dataframe(df, use_container_width=True)
            else: st.info("Guest not found.")

    # --- 2. STAFF PORTAL (GRE) ---
    elif mode == "Staff Portal (GRE)":
        st.title("🛎️ Staff Portal (GRE)")
        gre_name = st.text_input("Enter your GRE Name to access")
        if st.button("Access Portal"):
            gre_check = conn.query("SELECT * FROM gres WHERE gre_name ILIKE :n", params={"n": f"%{gre_name}%"}, ttl=0)
            if not gre_check.empty:
                st.success(f"Welcome, {gre_name}!")
                st.session_state.gre_user = gre_name
            else: st.error("Account not found.")
        
        if st.session_state.get("gre_user"):
            st.divider()
            guests_df = conn.query("SELECT id, name, arrival_time, room_cleaned, airport_pickup_sent FROM guests", ttl=0)
            st.dataframe(guests_df, use_container_width=True)
            with st.form("gre_update"):
                g_id = st.selectbox("Select Guest ID", guests_df['id'].tolist())
                rm = st.checkbox("Room Cleaned?")
                pk = st.checkbox("Pickup Sent?")
                if st.form_submit_button("Update"):
                    with conn.session as s:
                        s.execute(text("UPDATE guests SET room_cleaned = :r, airport_pickup_sent = :p WHERE id = :id"), {"r": int(rm), "p": int(pk), "id": g_id})
                        s.commit()
                    st.rerun()

    # --- 3. ADMIN PORTAL ---
    elif mode == "Admin Portal":
        cookie_manager = stx.CookieManager()
        saved_user = cookie_manager.get(cookie="admin_user")
        if saved_user and not st.session_state.logged_in:
            st.session_state.logged_in, st.session_state.user = True, saved_user

        if not st.session_state.logged_in:
            u, p = st.text_input("Username"), st.text_input("Password", type="password")
            if st.button("Login"):
                res = conn.query("SELECT * FROM admins WHERE username = :u AND password = :p", params={"u": u, "p": p}, ttl=0)
                if not res.empty:
                    st.session_state.logged_in, st.session_state.user = True, u
                    cookie_manager.set("admin_user", u, expires_at=datetime.datetime.now() + datetime.timedelta(days=30))
                    st.rerun()
                else: st.error("Invalid credentials.")
        
        if st.session_state.logged_in:
            colA, colB = st.columns([8, 1])
            colA.success(f"Welcome, {st.session_state.user}!")
            if colB.button("Logout"):
                st.session_state.logged_in = False
                cookie_manager.delete("admin_user")
                st.rerun()

            st.divider()
            raw_df = conn.query("SELECT * FROM guests", ttl=0)
            
            # --- DEFENSIVE COLUMN CHECK ---
            expected = ['category', 'speaker_category', 'accompanying_persons', 'poc', 'assigned_gre', 'departure_time']
            for col in expected:
                if col not in raw_df.columns: raw_df[col] = None 
            if not raw_df.empty:
                raw_df['arrival_dt'] = pd.to_datetime(raw_df['arrival_time'], format='%d/%m/%Y %H:%M', errors='coerce')

            st.title("🔍 Comprehensive Guest Search")
            f1, f2, f3 = st.columns([2, 2, 2])
            with f1: s_name = st.text_input("👤 Guest Name", placeholder="Search...")
            with f2:
                # Safely extract, clean, and sort categories (ignoring blanks and 'nan')
                if not raw_df.empty and 'category' in raw_df.columns:
                    available = sorted(list(set([str(c).strip() for c in raw_df['category'].dropna() if str(c).strip() not in ["", "nan", "None", "--"]])))
                else:
                    available = []
                s_cats = st.multiselect("🏷️ Categories", available)
            with f3:
                today = datetime.date.today()
                d_range = st.date_input("📅 Date Range", value=(today, today), format="DD/MM/YYYY")

            # Filtering logic
            filtered_df = raw_df.copy()
            if not filtered_df.empty:
                if s_name: filtered_df = filtered_df[filtered_df['name'].str.contains(s_name, case=False, na=False)]
                if s_cats: filtered_df = filtered_df[filtered_df['category'].isin(s_cats)]
                if isinstance(d_range, tuple) and len(d_range) == 2:
                    def to_dummy(dt):
                        if pd.isna(dt): return pd.NaT
                        return pd.Timestamp(year=2024, month=dt.month, day=dt.day)
                    d_start, d_end = to_dummy(d_range[0]), to_dummy(d_range[1])
                    filtered_df['dummy_date'] = filtered_df['arrival_dt'].apply(to_dummy)
                    filtered_df = filtered_df[(filtered_df['dummy_date'] >= d_start) & (filtered_df['dummy_date'] <= d_end) | filtered_df['arrival_dt'].isna()]

                st.divider()
                is_default = (not s_name) and (not s_cats) and (d_range == (today, today))
                
                if is_default:
                    st.subheader("📅 Today's Dashboard")
                    disp = raw_df[raw_df['arrival_dt'].dt.date == today] if not raw_df.empty else pd.DataFrame()
                    m1, m2, m3 = st.columns(3)
                    m1.metric("Total Arrivals", len(disp))
                    m2.metric("Pending Pickups", len(disp[disp['airport_pickup_sent'] == 0]) if not disp.empty else 0)
                    m3.metric("Dirty Rooms", len(disp[disp['room_cleaned'] == 0]) if not disp.empty else 0)
                else:
                    st.subheader("📊 Search Metrics")
                    disp = filtered_df
                    m1, m2 = st.columns(2)
                    m1.metric("Total Results", len(disp))
                    m2.metric("Speakers", len(disp[disp['speaker_category'] == 'Speaker']))
                    counts = disp['category'].dropna().value_counts()
                    if not counts.empty:
                        cols = st.columns(len(counts))
                        for i, (cn, count) in enumerate(counts.items()): cols[i].metric(cn, count)

                st.divider()

                if not disp.empty:
                    # --- BATCH ACTIONS TRIGGER ---
                    # Find out who is currently checked
                    selected_ids = [row['id'] for _, row in disp.iterrows() if st.session_state.get(f"chk_{row['id']}", False)]
                    
                    # Place the button neatly on the right side above the table
                    c1, c2 = st.columns([8, 2])
                    with c2:
                        if st.button(f"🛠️ Batch Actions ({len(selected_ids)})", use_container_width=True):
                            if len(selected_ids) > 0:
                                batch_actions_dialog(selected_ids)
                            else:
                                st.warning("Please check the box next to at least one guest first.")

                    # --- FULL WIDTH SEARCH RESULTS TABLE ---
                    # 1. Header wrapped in a bordered container
                    with st.container(border=True):
                        h0, h1, h2, h3, h4, h5 = st.columns([0.5, 3, 2, 2, 2, 1.5])
                        h0.write("**☑**")
                        h1.write("**Guest Name**")
                        h2.write("**GRE**")
                        h3.write("**POC**")
                        h4.write("**Arrival Time**")
                        h5.write("**Pax**")
                    
                    for _, row in disp.iterrows():
                        # 2. Every single row gets its own bordered container (Creates clean dividing lines)
                        with st.container(border=True):
                            r0, r1, r2, r3, r4, r5 = st.columns([0.5, 3, 2, 2, 2, 1.5])
                            
                            with r0:
                                st.checkbox(" ", key=f"chk_{row['id']}", label_visibility="collapsed")

                            # --- FLAG WARNING LOGIC ---
                            is_arriving_today = pd.notna(row['arrival_dt']) and row['arrival_dt'].date() == today
                            room_warning = is_arriving_today and not bool(row['room_cleaned'])
                            gre_warning = pd.isna(row['assigned_gre']) or str(row['assigned_gre']).strip() in ["", "-- Unassigned --", "None", "--"]
                            
                            flagged = room_warning or gre_warning
                            btn_type = "primary" if flagged else "secondary" 
                            
                            if gre_warning: icon = "🚨" 
                            elif room_warning: icon = "⚠️" 
                            else: icon = "👤" 

                            with r1:
                                if st.button(f"{icon} {row['name']}", key=f"btn_{row['id']}", type=btn_type, use_container_width=True): 
                                    ddp_dialog(row)
                                
                                # --- 3. REDUCED WARNING TEXT ---
                                # Using HTML to make the text smaller (12px) and tuck it directly under the button
                                if gre_warning:
                                    st.markdown("<p style='color: #ff4b4b; font-size: 12px; margin-top: -12px; margin-bottom: 0px;'><b>🚨 GRE NOT ASSIGNED</b></p>", unsafe_allow_html=True)
                                elif room_warning:
                                    st.markdown("<p style='color: #ff9800; font-size: 12px; margin-top: -12px; margin-bottom: 0px;'><b>⚠️ Room Not Cleaned</b></p>", unsafe_allow_html=True)
                                    
                            r2.write(row['assigned_gre'] if pd.notna(row['assigned_gre']) and str(row['assigned_gre']).strip() not in ["", "-- Unassigned --", "None", "--"] else "❌ Pending")
                            r3.write(row['poc'] or "--")
                            r4.write(row['arrival_time'] or "TBD")
                            r5.write(f"+{int(row['accompanying_persons']) if pd.notna(row['accompanying_persons']) else 0}")
                else: 
                    st.warning("No guests found.")

            # Bulk Tools
            st.divider()
            with st.expander("🛠️ Admin Tools (Add GRE / Bulk Import)"):
                t1, t2 = st.tabs(["Add GRE", "CSV Import"])
                with t1:
                    with st.form("gre_f"):
                        gn, gp = st.text_input("Name"), st.text_input("Phone")
                        if st.form_submit_button("Create"):
                            with conn.session as s:
                                s.execute(text("INSERT INTO gres (gre_name, gre_phone) VALUES (:n, :p)"), {"n": gn, "p": gp})
                                s.commit()
                            st.rerun()
                with t2:
                    # --- CSV FORMATTING GUIDE ---
                    st.info("""
                    📄 **CSV Column Guide:**
                    * **Required:** `name`, `admin_username`
                    * **Optional:** `poc`, `category`, `speaker_category`, `accompanying_persons`
                    """, icon="💡")
                    
                    f = st.file_uploader("Upload CSV", type="csv", key="bulk_csv_uploader")
                    f = st.file_uploader("Upload CSV", type="csv", key="bulk_csv_uploader")
                    if f:
                        data = pd.read_csv(f)
                        
                        # Standardize columns
                        data.columns = data.columns.str.lower().str.strip()
                        
                        if st.button("Run Import", type="primary"):
                            with conn.session as s:
                                for _, r in data.iterrows():
                                    g_name = str(r['name']).strip()
                                    a_user = str(r['admin_username']).strip()
                                    
                                    # Create Admin if doesn't exist
                                    s.execute(text("INSERT INTO admins (username, password) VALUES (:u, :p) ON CONFLICT DO NOTHING"), {"u": a_user, "p": "password123"})
                                    
                                    # Safely extract values (convert 'nan' back to empty string)
                                    cat_val = str(r['category']).strip() if 'category' in data.columns and pd.notna(r['category']) else ""
                                    if cat_val.lower() == "nan": cat_val = ""
                                    
                                    spk_val = str(r['speaker_category']).strip() if 'speaker_category' in data.columns and pd.notna(r['speaker_category']) else "Non-Speaker"
                                    if spk_val.lower() == "nan": spk_val = "Non-Speaker"
                                    
                                    poc_val = str(r['poc']).strip() if 'poc' in data.columns and pd.notna(r['poc']) else ""
                                    if poc_val.lower() == "nan": poc_val = ""
                                    
                                    try: pax_val = int(r['accompanying_persons']) if 'accompanying_persons' in data.columns and pd.notna(r['accompanying_persons']) else 0
                                    except: pax_val = 0

                                    # Check if guest already exists
                                    existing = s.execute(text("SELECT id FROM guests WHERE name = :n AND admin_owner = :u"), {"n": g_name, "u": a_user}).fetchone()
                                    
                                    if existing:
                                        # IF EXISTS: Update their missing data!
                                        s.execute(text("""
                                            UPDATE guests 
                                            SET category = :cat, speaker_category = :spk, poc = :poc, accompanying_persons = :pax
                                            WHERE id = :id
                                        """), {"cat": cat_val, "spk": spk_val, "poc": poc_val, "pax": pax_val, "id": existing[0]})
                                    else:
                                        # IF NEW: Insert them
                                        s.execute(text("""
                                            INSERT INTO guests (name, admin_owner, poc, category, speaker_category, accompanying_persons) 
                                            VALUES (:n, :u, :poc, :cat, :spk, :pax)
                                        """), {"n": g_name, "u": a_user, "poc": poc_val, "cat": cat_val, "spk": spk_val, "pax": pax_val})
                                        
                                s.commit()
                            st.success("CSV Processed! Existing guests updated and new guests added.")
                            st.rerun()

if __name__ == "__main__":
    main()
