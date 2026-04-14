import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import conn

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
