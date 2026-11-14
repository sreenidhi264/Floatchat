# load.py
# Loads processed and cleaned float, profile, and measurement data into SQLite

import sqlite3
import config

def get_connection():
    """Establish connection to the SQLite database."""
    # SQLite requires foreign keys to be explicitly enabled per connection
    conn = sqlite3.connect(config.DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON;")
    
    # Auto-initialize schema if tables do not exist
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='floats';")
    if not cur.fetchone():
        print("Database tables not found. Initializing database schema...")
        schema_file = config.BASE_DIR / "schema.sql"
        if schema_file.exists():
            with open(schema_file, "r") as f:
                conn.executescript(f.read())
            conn.commit()
            print("Database schema initialized successfully.")
        else:
            print(f"Warning: schema.sql not found at {schema_file}. Tables may be missing!")
    cur.close()
    
    return conn

def load_parsed_data(conn, parsed_data):
    """
    Loads parsed data (float, profile, and filtered measurements) into the SQLite DB.
    Uses database transactions.
    """
    float_meta = parsed_data["float"]
    profile_meta = parsed_data["profile"]
    measurements = parsed_data["measurements"]
    
    # In SQLite, dates and timestamps are stored as string ISO formats
    deployment_date_str = str(float_meta["deployment_date"]) if float_meta["deployment_date"] else None
    juld_str = profile_meta["juld"].isoformat() if profile_meta["juld"] else None
    
    cur = conn.cursor()
    try:
        # 1. Upsert Float Metadata
        float_sql = """
        INSERT INTO floats (platform_number, float_type, deployment_date)
        VALUES (?, ?, ?)
        ON CONFLICT (platform_number) DO UPDATE
        SET float_type = EXCLUDED.float_type,
            deployment_date = COALESCE(floats.deployment_date, EXCLUDED.deployment_date);
        """
        cur.execute(
            float_sql,
            (
                float_meta["platform_number"],
                float_meta["float_type"],
                deployment_date_str
            )
        )
        
        # 2. Upsert Profile Metadata
        profile_sql = """
        INSERT INTO profiles (platform_number, cycle_number, juld, latitude, longitude)
        VALUES (?, ?, ?, ?, ?)
        ON CONFLICT (platform_number, cycle_number) DO UPDATE
        SET juld = EXCLUDED.juld,
            latitude = EXCLUDED.latitude,
            longitude = EXCLUDED.longitude
        RETURNING profile_id;
        """
        cur.execute(
            profile_sql,
            (
                profile_meta["platform_number"],
                profile_meta["cycle_number"],
                juld_str,
                profile_meta["latitude"],
                profile_meta["longitude"]
            )
        )
        
        profile_id = cur.fetchone()[0]
        
        # 3. Clean existing measurements for this profile (to allow overwrites / updates)
        delete_sql = "DELETE FROM measurements WHERE profile_id = ?;"
        cur.execute(delete_sql, (profile_id,))
        
        # 4. Bulk Load Measurements using executemany
        if measurements:
            insert_sql = """
            INSERT INTO measurements (
                profile_id, pressure, pressure_qc, 
                temperature, temperature_qc, 
                salinity, salinity_qc, 
                oxygen, oxygen_qc, 
                chlorophyll, chlorophyll_qc
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?);
            """
            
            data_tuples = [
                (
                    profile_id,
                    m["pressure"],
                    m["pressure_qc"],
                    m["temperature"],
                    m["temperature_qc"],
                    m["salinity"],
                    m["salinity_qc"],
                    m["oxygen"],
                    m["oxygen_qc"],
                    m["chlorophyll"],
                    m["chlorophyll_qc"]
                )
                for m in measurements
            ]
            
            cur.executemany(insert_sql, data_tuples)
            
        return profile_id
        
    finally:
        cur.close()
