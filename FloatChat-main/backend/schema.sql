-- schema.sql
-- FloatChat Argo Float Database Schema (SQLite Version)

-- 1. Floats Table
-- Represents individual Argo floats
CREATE TABLE IF NOT EXISTS floats (
    platform_number TEXT PRIMARY KEY,
    float_type TEXT,                  -- 'core' or 'bgc'
    deployment_date TEXT              -- SQLite stores dates as ISO8601 TEXT strings
);

-- 2. Profiles Table
-- Represents individual cycle dives of a float
CREATE TABLE IF NOT EXISTS profiles (
    profile_id INTEGER PRIMARY KEY AUTOINCREMENT,
    platform_number TEXT REFERENCES floats(platform_number) ON DELETE CASCADE,
    cycle_number INTEGER NOT NULL,
    juld TEXT,                        -- SQLite stores timestamps as ISO8601 TEXT strings
    latitude REAL,
    longitude REAL,
    UNIQUE(platform_number, cycle_number)
);

-- Create index for quick lookups by float
CREATE INDEX IF NOT EXISTS idx_profiles_platform ON profiles(platform_number);
-- Create composite coordinate indexes for fast geographic range queries
CREATE INDEX IF NOT EXISTS idx_profiles_coords ON profiles(latitude, longitude);

-- 3. Measurements Table
-- Stores oceanographic observations for each pressure level in a profile
CREATE TABLE IF NOT EXISTS measurements (
    measurement_id INTEGER PRIMARY KEY AUTOINCREMENT,
    profile_id INTEGER REFERENCES profiles(profile_id) ON DELETE CASCADE,
    pressure REAL,
    pressure_qc INTEGER,
    temperature REAL,
    temperature_qc INTEGER,
    salinity REAL,
    salinity_qc INTEGER,
    oxygen REAL,
    oxygen_qc INTEGER,
    chlorophyll REAL,
    chlorophyll_qc INTEGER
);

-- Index measurements by profile_id to speed up retrieval of full profiles
CREATE INDEX IF NOT EXISTS idx_measurements_profile ON measurements(profile_id);
