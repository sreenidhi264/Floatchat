# config.py
# Configuration settings for FloatChat Backend Data Pipeline

import os
from pathlib import Path

# Base Directories
BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"
RAW_DIR = DATA_DIR / "raw"
LOGS_DIR = BASE_DIR / "logs"

# Ensure directories exist
DATA_DIR.mkdir(exist_ok=True)
RAW_DIR.mkdir(exist_ok=True)
LOGS_DIR.mkdir(exist_ok=True)

# Static Asset Directories for Visualizations
STATIC_DIR = BASE_DIR / "static"
PLOTS_DIR = STATIC_DIR / "plots"
MAPS_DIR = STATIC_DIR / "maps"

# Ensure static directories exist
STATIC_DIR.mkdir(exist_ok=True)
PLOTS_DIR.mkdir(exist_ok=True)
MAPS_DIR.mkdir(exist_ok=True)

# Database Connection Settings
# These can be overridden by environment variables
# Database Settings (SQLite Version)
DB_PATH = DATA_DIR / "floatchat.db"

# GDAC Server Settings (HTTP mirrors)
# US GDAC: https://usgodae.org/ftp/outgoing/argo
# French GDAC: https://data-argo.ifremer.fr
GDAC_BASE_URL = os.getenv("GDAC_BASE_URL", "https://data-argo.ifremer.fr")
GDAC_INDEX_URL = f"{GDAC_BASE_URL}/ar_index_global_prof.txt.gz"
GDAC_FILES_URL = f"{GDAC_BASE_URL}/dac"

# Manifest tracking to avoid downloading / parsing files twice
MANIFEST_FILE = DATA_DIR / "manifest.json"
FAILED_LOG_FILE = LOGS_DIR / "failed_files.log"

# Prototype / Small-scale Filtering Settings
# To keep the dataset manageable during development, we apply filters:
FILTER_DACS = ["incois"]  # INCOIS (India), containing Indian Ocean floats.
LIMIT_FILES = 2000      # Max profile files to download/process in a single run (None for unlimited)
FILTER_MIN_YEAR = 2021  # Filter profiles from 2021 onwards (last 5 years)

# Bounding box filter (optional, set to None or [min_lon, min_lat, max_lon, max_lat])
# Example for Arabian Sea / Bay of Bengal region: [50.0, 0.0, 95.0, 25.0]
FILTER_BBOX = [50.0, 0.0, 95.0, 25.0]

# Quality Control (QC) Flags to Keep
# Argo QC flags:
# 1 = Good data
# 2 = Probably good data
# 3 = Probably bad data
# 4 = Bad data
# We only want to keep 1 and 2
ACCEPTED_QC_FLAGS = [1, 2]
