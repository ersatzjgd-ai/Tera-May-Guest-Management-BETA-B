import streamlit as st
from database import conn, init_db
from search_tool import search_results_fragment
from admin_tools import admin_tools_fragment
from ddp_modal import ddp_dialog
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
        
        # Simple name-based login
        gre_name = st.text_input("Enter your full name to view your assigned guests")
        
        if gre_name:
            # Query guests matching the assigned GRE exactly by name
            df = conn.query("SELECT * FROM guests WHERE assigned_gre ILIKE :g", params={"g": gre_name.strip()}, ttl=0)
            
            if df.empty:
                st.warning(f"No guests currently assigned to '{gre_name}'. Please verify the spelling or check with an admin.")
            else:
                st.success(f"Welcome {gre_name}! You have {len(df)} assigned guests.")
                
                # Mobile-first vertical card layout for the on-ground staff
                for _, row in df.iterrows():
                    with st.container(border=True):
                        st.subheader(row['name'])
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.caption("Arrival")
                            st.write(f"{row['arrival_time'] if row['arrival_time'] else 'TBD'}")
                        with col2:
                            st.caption("Departure")
                            st.write(f"{row['departure_time'] if row['departure_time'] else 'TBD'}")
                            
                        # Restricted access: GRE can only open the DDP for their specific assigned guest
                        if st.button(f"Open Details for {row['name']}", key=f"gre_ddp_{row['id']}", use_container_width=True):
                            ddp_dialog(row.to_dict())

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
