import streamlit as st
import datetime
import os
import smtplib
from email.mime.text import MIMEText
import requests
import threading
from sqlalchemy import text
from database import conn

# --- External Notification Helpers (Run in background threads) ---

def _send_email_async(to_email, subject, text_body):
    """Sends an email via Gmail SMTP in the background."""
    smtp_user = os.environ.get("SMTP_USER") # e.g., yourevent.alerts@gmail.com
    smtp_pass = os.environ.get("SMTP_PASS") # Google App Password
    
    if not smtp_user or not smtp_pass or not to_email:
        return # Missing credentials or email, abort silently
        
    try:
        msg = MIMEText(text_body)
        msg['Subject'] = subject
        msg['From'] = smtp_user
        msg['To'] = str(to_email).strip()

        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

def _send_telegram_async(chat_id, text_body):
    """Sends a Telegram message via the Bot API in the background."""
    bot_token = os.environ.get("TG_BOT_TOKEN")
    
    if not bot_token or not chat_id:
        return # Missing token or chat ID, abort silently
        
    try:
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {"chat_id": str(chat_id).strip(), "text": text_body}
        requests.post(url, json=payload, timeout=5)
    except Exception as e:
        print(f"Failed to send Telegram to {chat_id}: {e}")


# --- Main Callbacks ---

def _create_notification(s, gid, subject, details):
    """Helper to create a DB notification AND trigger external alerts."""
    try:
        # 1. Fetch the guest name, admin owner, and assigned GRE
        guest = s.execute(text("SELECT name, admin_owner, assigned_gre FROM guests WHERE id = :id"), {"id": gid}).fetchone()
        
        if not guest: return
        gname, admin_owner, assigned_gre = guest[0], guest[1], guest[2]
        
        # 2. Always log to the Database dashboard for the Admin
        if admin_owner: 
            s.execute(text("""
                INSERT INTO notifications (admin_owner, guest_name, guest_id, subject, details) 
                VALUES (:owner, :gname, :gid, :sub, :det)
            """), {
                "owner": admin_owner, 
                "gname": gname, 
                "gid": gid,
                "sub": subject,
                "det": str(details)
            })

        # 3. Format the message for external pushing
        push_subject = f"🚨 Dignitary Alert: {subject} ({gname})"
        push_body = f"👤 Guest: {gname}\n🔔 Update: {subject}\n📝 Details: {details}"

        # 4. Push to Admin (if configured)
        if admin_owner:
            admin_prefs = s.execute(text("SELECT email, telegram_chat_id, notify_email, notify_telegram FROM admins WHERE username = :u"), {"u": admin_owner}).fetchone()
            if admin_prefs:
                a_email, a_tg, a_ne, a_nt = admin_prefs
                # Fire and forget using background threads
                if a_ne and a_email:
                    threading.Thread(target=_send_email_async, args=(a_email, push_subject, push_body)).start()
                if a_nt and a_tg:
                    threading.Thread(target=_send_telegram_async, args=(a_tg, push_body)).start()

        # 5. Push to GRE (if assigned and configured)
        if assigned_gre and assigned_gre not in ["", "-- Unassigned --", "None"]:
            gre_prefs = s.execute(text("SELECT email, telegram_chat_id, notify_email, notify_telegram FROM gres WHERE gre_name = :g"), {"g": assigned_gre}).fetchone()
            if gre_prefs:
                g_email, g_tg, g_ne, g_nt = gre_prefs
                # Fire and forget using background threads
                if g_ne and g_email:
                    threading.Thread(target=_send_email_async, args=(g_email, push_subject, push_body)).start()
                if g_nt and g_tg:
                    threading.Thread(target=_send_telegram_async, args=(g_tg, push_body)).start()

    except Exception as e:
        # Fail silently so we never break the main app if a notification fails
        print(f"Notification Error: {e}")
        pass

def db_update(field, widget_key, gid):
    val = st.session_state[widget_key]
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": val, "id": gid})
        
        # Format the field name nicely (e.g., 'gift_type' -> 'Gift Type Updated')
        friendly_field = field.replace('_', ' ').title()
        _create_notification(s, gid, f"{friendly_field} Updated", f"Changed to: {val}")
        
        s.commit()

def db_update_datetime(field, date_key, time_key, gid):
    d_val = st.session_state.get(date_key)
    t_val = st.session_state.get(time_key)
    if not d_val or not t_val: return 
    final_dt = datetime.datetime.combine(d_val, t_val)
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": final_dt, "id": gid})
        
        friendly_field = field.replace('_', ' ').title()
        dt_str = final_dt.strftime('%d %b, %H:%M')
        _create_notification(s, gid, f"{friendly_field} Updated", f"Scheduled for: {dt_str}")
        
        s.commit()

def update_gre_cb(widget_key, gid):
    val = st.session_state[widget_key]
    v = None if val == "-- Unassigned --" else val
    with conn.session as s:
        s.execute(text("UPDATE guests SET assigned_gre = :v WHERE id = :id"), {"v": v, "id": gid})
        _create_notification(s, gid, "GRE Assignment Updated", f"Assigned to: {v}")
        s.commit()

def toggle_room_cb(k, gid):
    val = int(st.session_state[k])
    with conn.session as s:
        s.execute(text("UPDATE guests SET room_cleaned = :r WHERE id = :id"), {"r": val, "id": gid})
        status = "Cleaned" if val else "Pending"
        _create_notification(s, gid, "Room Status Updated", f"Marked as {status}")
        s.commit()
    
def toggle_pk_cb(k, gid):
    val = int(st.session_state[k])
    with conn.session as s:
        s.execute(text("UPDATE guests SET airport_pickup_sent = :p WHERE id = :id"), {"p": val, "id": gid})
        status = "Sent" if val else "Pending"
        _create_notification(s, gid, "Pickup Status Updated", f"Marked as {status}")
        s.commit()

def toggle_ashram_cb(k, gid):
    val = int(st.session_state[k])
    with conn.session as s:
        s.execute(text("UPDATE guests SET ashram_tour = :a WHERE id = :id"), {"a": val, "id": gid})
        status = "Yes" if val else "No"
        _create_notification(s, gid, "Ashram Tour Updated", f"Set to {status}")
        s.commit()

def toggle_idc_cb(k, gid):
    val = int(st.session_state[k])
    with conn.session as s:
        s.execute(text("UPDATE guests SET id_card_issued = :i WHERE id = :id"), {"i": val, "id": gid})
        status = "Issued" if val else "Pending"
        _create_notification(s, gid, "ID Card Status Updated", f"Marked as {status}")
        s.commit()

def toggle_pin_cb(k, gid):
    val = int(st.session_state[k])
    with conn.session as s:
        s.execute(text("UPDATE guests SET remarks_pinned = :p WHERE id = :id"), {"p": val, "id": gid})
        status = "Pinned" if val else "Unpinned"
        _create_notification(s, gid, "Primary Remarks Toggled", f"Note is now {status}")
        s.commit()

def add_guest_note_cb(k, gid, admin_name):
    new_note = st.session_state[k]
    if new_note and new_note.strip():
        with conn.session as s:
            s.execute(text("INSERT INTO guest_notes (guest_id, admin_name, note_text, timestamp) VALUES (:gid, :admin, :note, :dt)"),
                      {"gid": gid, "admin": admin_name, "note": new_note.strip(), "dt": datetime.datetime.now()})
            _create_notification(s, gid, "New Log / Note Added", new_note.strip())
            s.commit()
        st.session_state[k] = ""
