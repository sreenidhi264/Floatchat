# verify_parser.py
# Offline test script to verify netCDF parsing and QC filtering on downloaded data

import json
from pathlib import Path
from parse import parse_argo_file
from qc_filter import filter_measurements

def main():
    # Find downloaded files
    raw_dir = Path("data/raw/incois")
    files = list(raw_dir.glob("**/*.nc"))
    
    if not files:
        print("No netCDF files found. Please run the ingestion script first.")
        return
        
    print(f"Found {len(files)} downloaded profile file(s).")
    
    for file_path in files:
        print(f"\n--- Testing parsing on: {file_path.name} ---")
        try:
            # 1. Test Ingestion & Parsing
            parsed = parse_argo_file(file_path)
            print("Successfully Parsed Metadata:")
            print(f"  Float ID:        {parsed['float']['platform_number']}")
            print(f"  Float Type:      {parsed['float']['float_type']}")
            print(f"  Cycle Number:    {parsed['profile']['cycle_number']}")
            print(f"  Date (Juld):     {parsed['profile']['juld']}")
            print(f"  Latitude:        {parsed['profile']['latitude']}")
            print(f"  Longitude:       {parsed['profile']['longitude']}")
            
            raw_count = len(parsed["measurements"])
            print(f"  Raw pressure levels: {raw_count}")
            
            # Print sample raw measurement (first level)
            if raw_count > 0:
                print("  Sample Raw Level (Level 1):")
                print(f"    {parsed['measurements'][0]}")
                
            # 2. Test QC Filtering
            filtered = filter_measurements(parsed["measurements"])
            filtered_count = len(filtered)
            print(f"  Filtered pressure levels (QC kept): {filtered_count}")
            
            if filtered_count > 0:
                print("  Sample Filtered Level (Level 1):")
                print(f"    {filtered[0]}")
                
        except Exception as e:
            print(f"Failed parsing/filtering test: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    main()
