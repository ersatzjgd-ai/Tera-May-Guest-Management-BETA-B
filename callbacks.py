import streamlit as st
import datetime
from sqlalchemy import text
from database import conn

def db_update(field, widget_key, gid):
    val = st.session_state[widget_key]
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": val, "id": gid})
        s.commit()

def db_update_datetime(field, date_key, time_key, gid):
    d_val = st.session_state.get(date_key)
    t_val = st.session_state.get(time_key)
    if not d_val or not t_val: return 
    final_dt = datetime.datetime.combine(d_val, t_val)
    with conn.session as s:
        s.execute(text(f"UPDATE guests SET {field} = :v WHERE id = :id"), {"v": final_dt, "id": gid})
        s.commit()

def update_gre_cb(widget_key, gid):
    val = st.session_state[widget_key]
    v = None if val == "-- Unassigned --" else val
    with conn.session as s:
        s.execute(text("UPDATE guests SET assigned_gre = :v WHERE id = :id"), {"v": v, "id": gid})
        s.commit()

def toggle_room_cb(k, gid):
    with conn.session as s:
        s.execute(text("UPDATE guests SET room_cleaned = :r WHERE id = :id"), {"r": int(st.session_state[k]), "id": gid})
        s.commit()
    
def toggle_pk_cb(k, gid):
    with conn.session as s:
        s.execute(text("UPDATE guests SET airport_pickup_sent = :p WHERE id = :id"), {"p": int(st.session_state[k]), "id": gid})
        s.commit()

def toggle_ashram_cb(k, gid):
    with conn.session as s:
        s.execute(text("UPDATE guests SET ashram_tour = :a WHERE id = :id"), {"a": int(st.session_state[k]), "id": gid})
        s.commit()

def toggle_pin_cb(k, gid):
    with conn.session as s:
        s.execute(text("UPDATE guests SET remarks_pinned = :p WHERE id = :id"), {"p": int(st.session_state[k]), "id": gid})
        s.commit()

def add_guest_note_cb(k, gid, admin_name):
    new_note = st.session_state[k]
    if new_note and new_note.strip():
        with conn.session as s:
            s.execute(text("INSERT INTO guest_notes (guest_id, admin_name, note_text, timestamp) VALUES (:gid, :admin, :note, :dt)"),
                      {"gid": gid, "admin": admin_name, "note": new_note.strip(), "dt": datetime.datetime.now()})
            s.commit()
        st.session_state[k] = ""
