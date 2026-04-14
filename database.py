import streamlit as st
from sqlalchemy import text

# --- INITIALIZE BUILT-IN SQL CONNECTION ---
conn = st.connection("postgresql", type="sql")

def init_db():
    """Ensure tables exist in Supabase and update them if needed"""
    with conn.session as s:
        s.execute(text('CREATE TABLE IF NOT EXISTS admins (username TEXT PRIMARY KEY, password TEXT);'))
        s.execute(text('CREATE TABLE IF NOT EXISTS gres (gre_id SERIAL PRIMARY KEY, gre_name TEXT, gre_phone TEXT);'))
        # Add the new POCs table here:
        s.execute(text('CREATE TABLE IF NOT EXISTS pocs (poc_id SERIAL PRIMARY KEY, poc_name TEXT UNIQUE, poc_phone TEXT);'))
        s.execute(text('''
            CREATE TABLE IF NOT EXISTS guests (
                id SERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                admin_owner TEXT,
                arrival_time TIMESTAMP,
                departure_time TIMESTAMP,
                airport_pickup_sent INTEGER DEFAULT 0,
                stay_location TEXT,
                room_cleaned INTEGER DEFAULT 0,
                assigned_gre TEXT,
                poc TEXT,
                housing TEXT DEFAULT 'TBD',
                gift_type TEXT DEFAULT 'Pending',
                ashram_tour INTEGER DEFAULT 0,
                remarks TEXT DEFAULT '',
                remarks_pinned INTEGER DEFAULT 0
            );
        '''))
        
        # --- NEW TABLE FOR AUDIT LOG / TIMELINE ---
        s.execute(text('''
            CREATE TABLE IF NOT EXISTS guest_notes (
                id SERIAL PRIMARY KEY,
                guest_id INTEGER,
                admin_name TEXT,
                note_text TEXT,
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
        '''))
        s.commit() 

    # --- FORCE SPEAKER CATEGORY TO TEXT ---
    with conn.session as s:
        try:
            s.execute(text("ALTER TABLE guests ALTER COLUMN speaker_category TYPE TEXT USING speaker_category::text;"))
            s.commit()
        except Exception:
            s.rollback()

    # --- MIGRATE DATES FROM TEXT TO TIMESTAMP ---
    with conn.session as s:
        try:
            # Safely cast arrival_time from TEXT to TIMESTAMP
            s.execute(text("""
                ALTER TABLE guests 
                ALTER COLUMN arrival_time TYPE TIMESTAMP 
                USING CASE 
                    WHEN arrival_time IS NULL OR TRIM(arrival_time) IN ('', 'TBD', 'None', 'nan') THEN NULL 
                    ELSE TO_TIMESTAMP(arrival_time, 'DD/MM/YYYY HH24:MI') 
                END;
            """))
            # Safely cast departure_time from TEXT to TIMESTAMP
            s.execute(text("""
                ALTER TABLE guests 
                ALTER COLUMN departure_time TYPE TIMESTAMP 
                USING CASE 
                    WHEN departure_time IS NULL OR TRIM(departure_time) IN ('', 'TBD', 'None', 'nan') THEN NULL 
                    ELSE TO_TIMESTAMP(departure_time, 'DD/MM/YYYY HH24:MI') 
                END;
            """))
            s.commit()
        except Exception:
            # If already converted or syntax fails, silently rollback to prevent crashing
            s.rollback()

    # --- ISOLATED TRANSACTIONS WITH ROLLBACKS ---
    columns_to_add = [
        ("departure_time", "TIMESTAMP"),
        ("poc", "TEXT"),
        ("assigned_gre", "TEXT"),
        ("category", "TEXT"),
        ("speaker_category", "TEXT"),
        ("accompanying_persons", "INTEGER DEFAULT 0"),
        ("housing", "TEXT DEFAULT 'TBD'"),
        ("gift_type", "TEXT DEFAULT 'Pending'"),
        ("ashram_tour", "INTEGER DEFAULT 0"),
        ("remarks", "TEXT DEFAULT ''"),
        ("remarks_pinned", "INTEGER DEFAULT 0")
    ]
    
    for col_name, col_type in columns_to_add:
        with conn.session as s:
            try:
                s.execute(text(f"ALTER TABLE guests ADD COLUMN {col_name} {col_type};"))
                s.commit()
            except Exception:
                s.rollback()
