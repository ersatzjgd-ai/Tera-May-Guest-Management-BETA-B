import streamlit as st
from database import conn, init_db
from search_tool import search_results_fragment
from admin_tools import admin_tools_fragment
import auth

def main():
    st.set_page_config(page_title="Dignitary Management", layout="wide", initial_sidebar_state="expanded")
    init_db()

    # --- 1. RUN AUTHENTICATION CHECK ---
    # This reads cookies instantly when the page loads
    auth.check_login_state()

    st.sidebar.title("🛂 Event Control")
    mode = st.sidebar.radio("Navigate to:", ["Public Search", "Staff Portal (GRE)", "Admin Portal"])

    # --- 2. SIDEBAR USER PROFILE & LOGOUT ---
    if st.session_state.logged_in:
        st.sidebar.divider()
        st.sidebar.markdown(f"👤 **Logged in as:** `{st.session_state.user}`")
        if st.sidebar.button("🚪 Secure Logout", use_container_width=True):
            auth.logout()

    # --- 3. ROUTING ---
    if mode == "Public Search":
        st.title("🛂 Guest Inquiry")
        search = st.text_input("Enter Guest Name")
        if search:
            df = conn.query("SELECT name, arrival_time, departure_time, housing FROM guests WHERE name ILIKE :n", params={"n": f"%{search}%"}, ttl=0)
            st.dataframe(df, use_container_width=True)

    elif mode == "Staff Portal (GRE)":
        st.title("🛎️ GRE Portal")
        gre_name = st.text_input("Enter GRE Name")
        if gre_name:
            st.info(f"Welcome {gre_name}. (Feature logic remains in main script for now).")

    elif mode == "Admin Portal":
        # If not logged in, show the new enterprise UI. Otherwise, show the dashboard!
        if not st.session_state.logged_in:
            auth.render_login()
        else:
            search_results_fragment()
            st.divider()
            admin_tools_fragment()

if __name__ == "__main__":
    main()
