# parse.py
# Opens Argo netCDF files, extracts measurements and metadata, and flattens them

import xarray as xr
import pandas as pd
import numpy as np
from pathlib import Path

def clean_string(val):
    """Decode bytes and strip whitespace from metadata values."""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="ignore")
    elif isinstance(val, np.ndarray):
        # Handle numpy character arrays
        val = "".join([c.decode("utf-8", errors="ignore") if isinstance(c, bytes) else str(c) for c in val])
    return str(val).strip()

def clean_qc_flag(val):
    """Convert character QC flags (e.g. b'1', '2') to integer, defaulting to 9 (missing/no QC)."""
    if isinstance(val, bytes):
        val = val.decode("utf-8", errors="ignore")
    val = str(val).strip()
    if val.isdigit():
        return int(val)
    return 9 # 9 is typically "missing value" in Argo QC

def parse_argo_file(file_path):
    """
    Parses a single Argo NetCDF file.
    Returns a dict with:
      - 'float': dict of float metadata
      - 'profile': dict of profile metadata
      - 'measurements': list of dicts of pressure level observations
    """
    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")
        
    # Open dataset using xarray. We use 'h5netcdf' or 'netcdf4' engine
    try:
        ds = xr.open_dataset(path, engine="netcdf4")
    except Exception as e1:
        try:
            ds = xr.open_dataset(path, engine="h5netcdf")
        except Exception as e2:
            raise IOError(f"Could not open netCDF file with netcdf4 or h5netcdf. Errors: {e1} | {e2}")

    try:
        # 1. Extract Float and Profile Metadata
        # Platform Number is often a 2D char array or a single string
        raw_platform = ds["PLATFORM_NUMBER"].values[0]
        platform_number = clean_string(raw_platform)
        
        cycle_number = int(ds["CYCLE_NUMBER"].values[0])
        
        # Julian Date (juld)
        raw_juld = ds["JULD"].values[0]
        # Handle datetime conversion
        if pd.isnull(raw_juld):
            juld = None
        else:
            juld = pd.to_datetime(raw_juld)
            if hasattr(juld, "to_pydatetime"):
                juld = juld.to_pydatetime()
            
        try:
            latitude = float(ds["LATITUDE"].values[0])
            longitude = float(ds["LONGITUDE"].values[0])
            # Check for fill values (Argo uses 99999.0 or similar)
            if latitude == 99999.0 or longitude == 99999.0 or np.isnan(latitude) or np.isnan(longitude):
                latitude, longitude = None, None
        except Exception:
            latitude, longitude = None, None
            
        # Determine float type based on parameters present in the file
        float_type = "core"
        bgc_indicators = ["DOXY", "CHLA", "NITRATE", "PH_IN_SITU_TOTAL"]
        for indicator in bgc_indicators:
            if indicator in ds:
                float_type = "bgc"
                break
                
        float_meta = {
            "platform_number": platform_number,
            "float_type": float_type,
            "deployment_date": juld.date() if juld else None
        }
        
        profile_meta = {
            "platform_number": platform_number,
            "cycle_number": cycle_number,
            "juld": juld,
            "latitude": latitude,
            "longitude": longitude
        }
        
        # 2. Extract measurements
        measurements = []
        n_levels = ds.sizes.get("N_LEVELS", 0)
        
        # Safely get variables if they exist
        pres = ds["PRES"].values[0] if "PRES" in ds else None
        pres_qc = ds["PRES_QC"].values[0] if "PRES_QC" in ds else None
        temp = ds["TEMP"].values[0] if "TEMP" in ds else None
        temp_qc = ds["TEMP_QC"].values[0] if "TEMP_QC" in ds else None
        psal = ds["PSAL"].values[0] if "PSAL" in ds else None
        psal_qc = ds["PSAL_QC"].values[0] if "PSAL_QC" in ds else None
        
        # BGC parameters
        doxy = ds["DOXY"].values[0] if "DOXY" in ds else None
        doxy_qc = ds["DOXY_QC"].values[0] if "DOXY_QC" in ds else None
        chla = ds["CHLA"].values[0] if "CHLA" in ds else None
        chla_qc = ds["CHLA_QC"].values[0] if "CHLA_QC" in ds else None
        
        for lvl in range(n_levels):
            # Extract pressure (must have a pressure to be valid depth level)
            p_val = float(pres[lvl]) if pres is not None else np.nan
            if np.isnan(p_val) or p_val == 99999.0:
                continue
                
            p_qc = clean_qc_flag(pres_qc[lvl]) if pres_qc is not None else 9
            
            # Temperature
            t_val = float(temp[lvl]) if temp is not None else np.nan
            if np.isnan(t_val) or t_val == 99999.0:
                t_val = None
            t_qc = clean_qc_flag(temp_qc[lvl]) if temp_qc is not None else 9
            
            # Salinity
            s_val = float(psal[lvl]) if psal is not None else np.nan
            if np.isnan(s_val) or s_val == 99999.0:
                s_val = None
            s_qc = clean_qc_flag(psal_qc[lvl]) if psal_qc is not None else 9
            
            # Oxygen (BGC)
            o_val = float(doxy[lvl]) if doxy is not None else np.nan
            if np.isnan(o_val) or o_val == 99999.0:
                o_val = None
            o_qc = clean_qc_flag(doxy_qc[lvl]) if doxy_qc is not None else 9
            
            # Chlorophyll (BGC)
            c_val = float(chla[lvl]) if chla is not None else np.nan
            if np.isnan(c_val) or c_val == 99999.0:
                c_val = None
            c_qc = clean_qc_flag(chla_qc[lvl]) if chla_qc is not None else 9
            
            # Skip rows where core metrics are completely missing
            if t_val is None and s_val is None and o_val is None and c_val is None:
                continue
                
            measurements.append({
                "pressure": p_val,
                "pressure_qc": p_qc,
                "temperature": t_val,
                "temperature_qc": t_qc,
                "salinity": s_val,
                "salinity_qc": s_qc,
                "oxygen": o_val,
                "oxygen_qc": o_qc,
                "chlorophyll": c_val,
                "chlorophyll_qc": c_qc
            })
            
        return {
            "float": float_meta,
            "profile": profile_meta,
            "measurements": measurements
        }
        
    finally:
        ds.close()

if __name__ == "__main__":
    # Test stub
    import sys
    if len(sys.argv) > 1:
        test_file = sys.argv[1]
        try:
            res = parse_argo_file(test_file)
            print("Float Meta:", res["float"])
            print("Profile Meta:", res["profile"])
            print(f"Parsed {len(res['measurements'])} measurement levels.")
        except Exception as e:
            print(f"Error parsing file: {e}")
    else:
        print("Usage: python parse.py <path_to_netcdf_file>")
