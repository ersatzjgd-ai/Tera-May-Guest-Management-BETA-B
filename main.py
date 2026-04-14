import streamlit as st
from database import conn, init_db
from search_tool import search_results_fragment
from admin_tools import admin_tools_fragment

def main():
    st.set_page_config(page_title="Dignitary Management", layout="wide")
    init_db()

    if "logged_in" not in st.session_state: st.session_state.logged_in = False

    st.sidebar.title("🛂 Event Control")
    mode = st.sidebar.radio("Navigate to:", ["Public Search", "Staff Portal (GRE)", "Admin Portal"])

    if mode == "General Guest Search":
        st.title("🛂 Guest Inquiry")
        search = st.text_input("Enter Guest Name")
        if search:
            df = conn.query("SELECT name, arrival_time, departure_time, housing FROM guests WHERE name ILIKE :n", params={"n": f"%{search}%"}, ttl=0)
            st.dataframe(df, use_container_width=True)

    elif mode == "GRE Portal)":
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
