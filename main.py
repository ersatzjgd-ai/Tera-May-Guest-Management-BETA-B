import streamlit as st
import pandas as pd
from sqlalchemy import text
from database import conn, init_db
from search_tool import search_results_fragment
from admin_tools import admin_tools_fragment
from ddp_modal import ddp_dialog, mobile_ddp_dialog
import auth

def main():
    st.set_page_config(page_title="Dignitary Management", layout="wide", initial_sidebar_state="expanded")
    init_db()

    # --- 1. RUN AUTHENTICATION CHECK ---
    # This reads cookies instantly when the page loads
    auth.check_login_state()

    st.sidebar.title("🛂 Event Control")
    
    # BUG FIX: Added key="main_nav" so Streamlit remembers your page across reruns
    mode = st.sidebar.radio("Navigate to:", ["Public Search", "Staff Portal (GRE)", "Admin Portal"], key="main_nav")

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
            # Query guests matching the assigned GRE with a partial match (wildcards)
            df = conn.query("SELECT * FROM guests WHERE assigned_gre ILIKE :g", params={"g": f"%{gre_name.strip()}%"}, ttl=0)
            
            if df.empty:
                st.warning(f"No guests currently assigned to '{gre_name}'. Please verify the spelling or check with an admin.")
            else:
                st.success(f"Welcome {gre_name}! You have {len(df)} assigned guests.")

                # --- NEW: GRE NOTIFICATION SETTINGS ---
                gre_db_df = conn.query("SELECT * FROM gres WHERE gre_name ILIKE :g LIMIT 1", params={"g": f"%{gre_name.strip()}%"}, ttl=0)
                if not gre_db_df.empty:
                    gre_record = gre_db_df.iloc[0]
                    with st.expander("⚙️ My Notification Settings"):
                        with st.form(key=f"gre_settings_form_{gre_record['gre_id']}"):
                            # Safely handle potential null values from the database
                            curr_email = "" if pd.isna(gre_record.get('email')) else str(gre_record.get('email'))
                            curr_tg = "" if pd.isna(gre_record.get('telegram_chat_id')) else str(gre_record.get('telegram_chat_id'))
                            curr_ne = True if pd.isna(gre_record.get('notify_email')) else bool(gre_record.get('notify_email'))
                            curr_nt = False if pd.isna(gre_record.get('notify_telegram')) else bool(gre_record.get('notify_telegram'))
                            
                            new_email = st.text_input("📧 Email Address", value=curr_email)
                            st.caption("Tip: Use the email that's on your mobile phone")
                            
                            new_tg = st.text_input("✈️ Telegram Chat ID", value=curr_tg)
                            st.caption("Don't know your ID? Message @YourEventBot on Telegram and say 'Start'!")
                            
                            c1, c2 = st.columns(2)
                            with c1: opt_email = st.toggle("Receive Email Alerts", value=curr_ne)
                            with c2: opt_tg = st.toggle("Receive Telegram Alerts", value=curr_nt)
                            
                            if st.form_submit_button("Save Preferences", use_container_width=True):
                                with conn.session as s:
                                    s.execute(text("""
                                        UPDATE gres SET 
                                        email = :e, telegram_chat_id = :t, notify_email = :ne, notify_telegram = :nt 
                                        WHERE gre_id = :gid
                                    """), {"e": new_email, "t": new_tg, "ne": opt_email, "nt": opt_tg, "gid": int(gre_record['gre_id'])})
                                    s.commit()
                                st.success("Settings saved successfully!")
                                st.rerun()
                
                st.write("") # Quick spacing buffer before the guest cards

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
                            mobile_ddp_dialog(row.to_dict())

    elif mode == "Admin Portal":
        # If not logged in, show the new enterprise UI. Otherwise, show the dashboard!
        if not st.session_state.logged_in:
            auth.render_login()
        else:
            current_admin = st.session_state.user
            
            # Fetch admin gender to format the greeting
            admin_data = conn.query("SELECT gender FROM admins WHERE username = :u", params={"u": current_admin}, ttl=0)
            admin_gender = None
            if not admin_data.empty:
                admin_gender = admin_data.iloc[0]['gender']
                
            suffix = ""
            if admin_gender:
                gender_str = str(admin_gender).strip().upper()
                if gender_str in ["M", "MALE"]:
                    suffix = " Bhaiya"
                elif gender_str in ["F", "FEMALE"]:
                    suffix = " Didi"
            
            # Capitalize the username for a nicer display
            display_name = str(current_admin).title()
            
            # Inject professional font CSS
            st.markdown("""
            <style>
            .traditional-greeting {
                font-family: system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
                font-weight: 400; /* Reduced from 500 to normal to make it less bold */
                font-size: 13px; /* Reduced slightly to make it less prominent */
                color: #d97706; /* Warm saffron/orange hue */
                margin-top: -35px; /* Pulls the greeting up closer to the top */
                margin-bottom: 10px;
                line-height: 1.2;
                opacity: 0.85; /* Slight opacity drop for less prominence */
            }
            </style>
            """, unsafe_allow_html=True)
            
            # --- NOTIFICATIONS & DASHBOARD HEADER ---
            col_hdr, col_notif = st.columns([9, 2])
            with col_hdr:
                st.markdown(f'<div class="traditional-greeting">Jai Gurudev {display_name}{suffix} 🙏</div>', unsafe_allow_html=True)
            
            with col_notif:
                st.write("") # Padding to push it down slightly
                # Fetch up to 20 recent notifications (both read and unread)
                notifs_df = conn.query("SELECT * FROM notifications WHERE admin_owner = :admin ORDER BY timestamp DESC LIMIT 20", params={"admin": current_admin}, ttl=0)
                unread_count = len(notifs_df[notifs_df['is_read'] == False]) if not notifs_df.empty else 0
                
                with st.popover(f"🔔 {unread_count} Unread", use_container_width=True):
                    if unread_count > 0:
                        if st.button("✔️ Mark All as Read", use_container_width=True):
                            with conn.session as s:
                                s.execute(text("UPDATE notifications SET is_read = TRUE WHERE admin_owner = :admin AND is_read = FALSE"), {"admin": current_admin})
                                s.commit()
                            st.rerun()
                        st.divider()
                        
                    if notifs_df.empty:
                        st.info("No notifications.")
                    else:
                        for _, notif in notifs_df.iterrows():
                            if not notif['is_read']:
                                # --- UNREAD FORMAT (Detailed) ---
                                st.markdown(f"**{notif['subject']}**")
                                st.caption(f"👤 **{notif['guest_name']}**<br>{notif['details']}", unsafe_allow_html=True)
                                
                                if st.button("View Guest DDP", key=f"btn_notif_{notif['id']}", use_container_width=True):
                                    # Fetch fresh guest data to pass to the DDP dialog
                                    g_df = conn.query("SELECT * FROM guests WHERE id = :id", params={"id": notif['guest_id']}, ttl=0)
                                    if not g_df.empty:
                                        ddp_dialog(g_df.iloc[0].to_dict())
                                        
                                st.markdown("<hr style='margin: 8px 0;'>", unsafe_allow_html=True)
                            else:
                                # --- READ FORMAT (Compact / Grayed Out) ---
                                st.markdown(f"<div style='color: #888; font-size: 13px; margin-bottom: 4px;'>{notif['subject']} — <i>{notif['guest_name']}</i></div>", unsafe_allow_html=True)
                                st.markdown("<hr style='margin: 4px 0; border-color: #eee;'>", unsafe_allow_html=True)

            # --- NEW: ADMIN NOTIFICATION SETTINGS ---
            admin_info = conn.query("SELECT email, telegram_chat_id, notify_email, notify_telegram FROM admins WHERE username = :u", params={"u": current_admin}, ttl=0)
            with st.expander("⚙️ My Notification Settings"):
                if not admin_info.empty:
                    a_record = admin_info.iloc[0]
                    with st.form(key="admin_settings_form"):
                        curr_email = "" if pd.isna(a_record.get('email')) else str(a_record.get('email'))
                        curr_tg = "" if pd.isna(a_record.get('telegram_chat_id')) else str(a_record.get('telegram_chat_id'))
                        curr_ne = True if pd.isna(a_record.get('notify_email')) else bool(a_record.get('notify_email'))
                        curr_nt = False if pd.isna(a_record.get('notify_telegram')) else bool(a_record.get('notify_telegram'))
                        
                        new_email = st.text_input("📧 Email Address", value=curr_email)
                        st.caption("Tip: Use the email that's on your mobile phone")
                        
                        new_tg = st.text_input("✈️ Telegram Chat ID", value=curr_tg)
                        st.caption("Don't know your ID? Message @YourEventBot on Telegram and say 'Start'!")
                        
                        c1, c2 = st.columns(2)
                        with c1: opt_email = st.toggle("Receive Email Alerts", value=curr_ne)
                        with c2: opt_tg = st.toggle("Receive Telegram Alerts", value=curr_nt)
                        
                        if st.form_submit_button("Save Preferences", use_container_width=True):
                            with conn.session as s:
                                s.execute(text("""
                                    UPDATE admins SET 
                                    email = :e, telegram_chat_id = :t, notify_email = :ne, notify_telegram = :nt 
                                    WHERE username = :u
                                """), {"e": new_email, "t": new_tg, "ne": opt_email, "nt": opt_tg, "u": current_admin})
                                s.commit()
                            st.success("Settings saved successfully!")
                            st.rerun()

            search_results_fragment()
            st.divider()
            admin_tools_fragment()

if __name__ == "__main__":
    main()
