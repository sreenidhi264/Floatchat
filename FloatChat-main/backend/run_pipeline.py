# run_pipeline.py
# End-to-end orchestrator for the FloatChat data pipeline

import os
import argparse
import sys
from pathlib import Path
import config
from ingest import run_ingestion, load_manifest, save_manifest
from parse import parse_argo_file
from qc_filter import filter_measurements
from load import get_connection, load_parsed_data

def log_failure(file_path, error_msg):
    """Log failures to a persistent file."""
    with open(config.FAILED_LOG_FILE, "a") as log:
        log.write(f"File: {file_path} | Error: {error_msg}\n")

def process_file(conn, file_path):
    """Parses, filters, and loads a single NetCDF file."""
    try:
        # Step 2: Parse NetCDF file
        parsed = parse_argo_file(file_path)
        
        # Step 3: Filter data using Quality Control flags
        original_count = len(parsed["measurements"])
        parsed["measurements"] = filter_measurements(parsed["measurements"])
        filtered_count = len(parsed["measurements"])
        
        # Step 4: Load into database
        profile_id = load_parsed_data(conn, parsed)
        
        print(f"  -> Success: Loaded profile ID {profile_id} for float {parsed['float']['platform_number']} cycle {parsed['profile']['cycle_number']}. "
              f"Measurements: {filtered_count}/{original_count} kept.")
        return True
    except Exception as e:
        print(f"  -> Failed: {file_path}. Error: {e}")
        log_failure(file_path, str(e))
        return False

def main():
    parser = argparse.ArgumentParser(description="FloatChat NetCDF -> PostgreSQL Ingestion Pipeline")
    parser.add_argument("--full", action="store_true", help="Bypass manifest and run a full check / re-ingestion.")
    parser.add_argument("--incremental", action="store_true", default=True, help="Only fetch new files (default).")
    parser.add_argument("--limit", type=int, default=None, help="Overriding limit for the maximum number of files to process.")
    parser.add_argument("--clear-manifest", action="store_true", help="Clear the manifest to force a full reload of downloaded files.")
    
    args = parser.parse_args()
    
    # 1. Handle manifest resetting
    if args.clear_manifest:
        print("Clearing local manifest...")
        if config.MANIFEST_FILE.exists():
            config.MANIFEST_FILE.unlink()
        print("Manifest cleared.")
        
    if args.full:
        print("Running in FULL mode (will download and re-process matching files).")
        # In full mode we clear/ignore manifest to download
        manifest = {}
    else:
        print("Running in INCREMENTAL mode (processing new files only).")
        manifest = load_manifest()
        
    # Use overriding limit if specified, else fall back to config
    limit = args.limit if args.limit is not None else config.LIMIT_FILES
    
    # 2. Run Ingestion (downloads new netCDF files)
    print("=== Step 1: Running Ingestion ===")
    downloaded_files = run_ingestion(limit=limit)
    if not downloaded_files:
        print("No new files to process. Pipeline exiting.")
        return
        
    # 3. Establish DB Connection
    print("=== Step 2: Processing and Loading Files ===")
    try:
        conn = get_connection()
        conn.autocommit = False # Use transactions
    except Exception as e:
        print(f"Database Connection Error: {e}")
        print("Please check your PostgreSQL settings in config.py or environment variables.")
        sys.exit(1)
        
    success_count = 0
    failure_count = 0
    
    try:
        for idx, file_path in enumerate(downloaded_files):
            print(f"[{idx+1}/{len(downloaded_files)}] Processing {Path(file_path).name}...")
            # Run single file processing inside its own transaction
            success = process_file(conn, file_path)
            if success:
                conn.commit()
                success_count += 1
            else:
                conn.rollback()
                failure_count += 1
                
    finally:
        conn.close()
        
    print("=== Ingestion Summary ===")
    print(f"Total files downloaded: {len(downloaded_files)}")
    print(f"Successfully loaded:  {success_count}")
    print(f"Failed loading:      {failure_count} (logged in {config.FAILED_LOG_FILE.name})")

if __name__ == "__main__":
    main()
