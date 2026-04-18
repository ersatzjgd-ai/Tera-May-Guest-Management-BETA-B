import streamlit as st
import datetime
from sqlalchemy import text
from database import conn

def _create_notification(s, gid, subject, details):
    """Helper to create a notification within the current DB session."""
    try:
        # Fetch the guest name and admin owner using the guest ID
        guest = s.execute(text("SELECT name, admin_owner FROM guests WHERE id = :id"), {"id": gid}).fetchone()
        
        # Only create a notification if the guest is assigned to an admin
        if guest and guest[1]: 
            s.execute(text("""
                INSERT INTO notifications (admin_owner, guest_name, guest_id, subject, details) 
                VALUES (:owner, :gname, :gid, :sub, :det)
            """), {
                "owner": guest[1],   # admin_owner
                "gname": guest[0],   # guest_name
                "gid": gid,
                "sub": subject,
                "det": str(details)
            })
    except Exception:
        # Fail silently so we never break the main app if a notification fails to log
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
