# ingest.py
# Downloads the Argo index and retrieves netCDF files based on filtering rules

import os
import gzip
import json
import urllib.request
import urllib.error
import ssl
from pathlib import Path
import config

# Bypass SSL verification to prevent certificate errors on some environments
try:
    ssl._create_default_https_context = ssl._create_unverified_context
except AttributeError:
    pass

def load_manifest():
    """Load the local manifest file to track already processed files."""
    if config.MANIFEST_FILE.exists():
        try:
            with open(config.MANIFEST_FILE, "r") as f:
                return json.load(f)
        except Exception as e:
            print(f"Warning: Failed to load manifest, starting fresh. Error: {e}")
    return {}

def save_manifest(manifest):
    """Save the manifest back to disk."""
    with open(config.MANIFEST_FILE, "w") as f:
        json.dump(manifest, f, indent=4)

def download_index():
    """Download the global Argo index file."""
    local_index_path = config.DATA_DIR / "ar_index_global_prof.txt.gz"
    print(f"Downloading index from {config.GDAC_INDEX_URL}...")
    try:
        urllib.request.urlretrieve(config.GDAC_INDEX_URL, local_index_path)
        print("Index downloaded successfully.")
        return local_index_path
    except Exception as e:
        print(f"Error downloading index: {e}")
        return None

def parse_and_filter_index(local_index_path, manifest, limit=config.LIMIT_FILES):
    """
    Parses the index file and returns a list of files that match our filters
    and need to be downloaded or updated.
    """
    files_to_download = []
    
    print("Parsing and filtering index...")
    # Open gzipped index file
    with gzip.open(local_index_path, "rt", encoding="utf-8", errors="ignore") as f:
        header_found = False
        headers = []
        
        for line in f:
            line = line.strip()
            # Skip comments or empty lines
            if not line or line.startswith("#"):
                continue
                
            if not header_found:
                # First non-comment line is the header
                headers = line.split(",")
                header_found = True
                continue
            
            # Data row
            parts = line.split(",")
            if len(parts) < len(headers):
                continue
                
            row = dict(zip(headers, parts))
            file_path = row.get("file")
            date_update = row.get("date_update")
            
            if not file_path:
                continue
                
            # Filter 1: DAC (e.g. "in" for INCOIS)
            dac = file_path.split("/")[0]
            if config.FILTER_DACS and dac not in config.FILTER_DACS:
                continue
                
            # Filter 2: Bounding Box (latitude / longitude)
            if config.FILTER_BBOX:
                try:
                    lat = float(row.get("latitude"))
                    lon = float(row.get("longitude"))
                    min_lon, min_lat, max_lon, max_lat = config.FILTER_BBOX
                    if not (min_lon <= lon <= max_lon and min_lat <= lat <= max_lat):
                        continue
                except (ValueError, TypeError):
                    # If coordinates are missing or corrupt, skip to be safe
                    continue
            
            # Filter 3: Min Year (last 5 years)
            if hasattr(config, "FILTER_MIN_YEAR") and config.FILTER_MIN_YEAR:
                date_str = row.get("date")
                if date_str:
                    try:
                        year = int(date_str[:4])
                        if year < config.FILTER_MIN_YEAR:
                            continue
                    except ValueError:
                        continue
            
            # Check manifest to see if we already have the latest version of this file
            if file_path in manifest and manifest[file_path] == date_update:
                # File already downloaded and loaded, skip
                continue
                
            files_to_download.append((file_path, date_update))
            
            # Stop if we hit the limit
            if limit and len(files_to_download) >= limit:
                print(f"Reached prototype file limit of {limit} files.")
                break
                
    print(f"Found {len(files_to_download)} new/updated files to download.")
    return files_to_download

def download_files(files_to_download):
    """Downloads NetCDF files from the GDAC HTTP server and returns success list."""
    downloaded_files = []
    manifest = load_manifest()
    
    for file_path, date_update in files_to_download:
        remote_url = f"{config.GDAC_FILES_URL}/{file_path}"
        local_path = config.RAW_DIR / file_path
        
        # Ensure subdirectory exists (e.g., raw/in/2902123/profiles/)
        local_path.parent.mkdir(parents=True, exist_ok=True)
        
        print(f"Downloading {file_path}...")
        try:
            urllib.request.urlretrieve(remote_url, local_path)
            # Update manifest local record
            manifest[file_path] = date_update
            downloaded_files.append(local_path)
        except urllib.error.HTTPError as he:
            print(f"HTTP Error {he.code} for {file_path}. Skipping.")
        except Exception as e:
            print(f"Failed to download {file_path}. Error: {e}")
            
    # Save updated manifest
    save_manifest(manifest)
    return downloaded_files

def run_ingestion(limit=config.LIMIT_FILES):
    """Main ingestion coordinator."""
    manifest = load_manifest()
    index_path = download_index()
    if not index_path:
        print("Ingestion failed: Index file could not be downloaded.")
        return []
        
    to_download = parse_and_filter_index(index_path, manifest, limit)
    if not to_download:
        print("No new files to ingest.")
        return []
        
    downloaded = download_files(to_download)
    print(f"Ingestion completed. Downloaded {len(downloaded)} files.")
    return downloaded

if __name__ == "__main__":
    run_ingestion()
