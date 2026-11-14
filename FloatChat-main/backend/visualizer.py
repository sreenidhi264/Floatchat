# visualizer.py
# Generates high-fidelity, premium dark-mode plots and maps from SQLite data

import sqlite3
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import folium
from pathlib import Path
from scipy.interpolate import make_interp_spline
import config

def get_db_connection():
    """Open a read-only connection — visualizer only ever reads data."""
    db_uri = f"file:{config.DB_PATH.as_posix()}?mode=ro"
    return sqlite3.connect(db_uri, uri=True)

def apply_dark_theme(fig, ax):
    """Applies a premium, modern dark ocean theme to a matplotlib chart."""
    bg_color = '#0B0F19'       # Deep Space/Ocean Navy
    grid_color = '#1C2333'     # Muted Grid Navy
    text_color = '#E2E8F0'     # Soft Off-White
    
    fig.patch.set_facecolor(bg_color)
    ax.set_facecolor(bg_color)
    
    # Grid lines
    ax.grid(True, linestyle='--', color=grid_color, alpha=0.7)
    
    # Tick colors and labels
    ax.tick_params(colors=text_color, labelsize=9)
    ax.xaxis.label.set_color(text_color)
    ax.yaxis.label.set_color(text_color)
    
    # Title color
    if ax.title:
        ax.title.set_color(text_color)
        
    # Borders (spines) formatting - keep only a clean thin border
    for spine in ax.spines.values():
        spine.set_color('#1C2333')
        spine.set_linewidth(1.5)
        
    return text_color

def plot_depth_profile(platform_number, cycle_number, parameter='temperature'):
    """
    Plots a high-fidelity, smooth vertical profile chart for a parameter.
    Y-axis is inverted. Background is styled in premium dark mode.
    """
    # FIX (#3): Use a safe whitelist dict instead of f-string interpolation.
    # param_col comes from AI-generated output which is influenced by user input —
    # directly interpolating it into SQL is a SQL injection vector.
    SAFE_PARAM_COLS = {
        'temperature': 'temperature',
        'salinity':    'salinity',
        'oxygen':      'oxygen',
        'chlorophyll': 'chlorophyll',
    }
    param_col = parameter.lower()
    if param_col not in SAFE_PARAM_COLS:
        raise ValueError(f"Invalid parameter name: {parameter}")
    safe_col = SAFE_PARAM_COLS[param_col]   # provably a safe literal column name

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # safe_col is sourced from the hardcoded whitelist dict above, never from user input
        query = f"""
        SELECT m.pressure, m.{safe_col}
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.profile_id
        WHERE p.platform_number = ? AND p.cycle_number = ?
        ORDER BY m.pressure ASC;
        """
        cur.execute(query, (platform_number, cycle_number))
        rows = cur.fetchall()
    finally:
        # FIX (#2): Always close, even if the query raises.
        if conn:
            conn.close()
    
    if not rows:
        raise ValueError(f"No measurements found for float {platform_number} cycle {cycle_number}")
        
    # Extract and clean data
    pressures = [r[0] for r in rows]
    values = [r[1] for r in rows]
    
    valid_data = [(v, p) for v, p in zip(values, pressures) if v is not None and p is not None]
    if not valid_data:
        raise ValueError(f"No valid {parameter} data found for float {platform_number} cycle {cycle_number}")
        
    vals_raw, press_raw = zip(*valid_data)
    
    # 1. Remove duplicate pressures to prevent interpolation errors
    unique_points = {}
    for p, v in zip(press_raw, vals_raw):
        if p not in unique_points:
            unique_points[p] = v
            
    press_sorted = sorted(unique_points.keys())
    vals_sorted = [unique_points[p] for p in press_sorted]
    
    # 2. Apply Cubic Spline Interpolation for smooth curves
    if len(press_sorted) > 3:
        press_smooth = np.linspace(min(press_sorted), max(press_sorted), 300)
        try:
            spline = make_interp_spline(press_sorted, vals_sorted, k=3)
            vals_smooth = spline(press_smooth)
        except Exception:
            # Fallback to linear if spline fails
            press_smooth = press_sorted
            vals_smooth = vals_sorted
    else:
        press_smooth = press_sorted
        vals_smooth = vals_sorted
        
    # Plot setup
    fig, ax = plt.subplots(figsize=(6, 8))
    
    # Neon Color Palette
    color_map = {
        'temperature': '#FF5A36',  # Glowing Coral/Orange
        'salinity': '#00D2FF',     # Electric Cyan
        'oxygen': '#BF5AF2',       # Neon Purple
        'chlorophyll': '#30D158'   # Bio Green
    }
    unit_map = {
        'temperature': 'Temperature (°C)',
        'salinity': 'Salinity (psu)',
        'oxygen': 'Oxygen (µmol/kg)',
        'chlorophyll': 'Chlorophyll (mg/m³)'
    }
    
    color = color_map[param_col]
    
    # Plot smooth line and translucent filled shadow
    ax.plot(vals_smooth, press_smooth, color=color, linewidth=2.5, label=f"Smooth Curve (k=3)")
    ax.fill_betweenx(press_smooth, vals_smooth, color=color, alpha=0.12)
    
    # Scatter raw actual readings as subtle dots to show real data points
    ax.scatter(vals_sorted, press_sorted, color=color, s=15, alpha=0.8, edgecolors='#ffffff', linewidths=0.5, label='Actual Readings')
    
    # Apply Premium Dark Theme
    apply_dark_theme(fig, ax)
    
    # Titles & Labels
    ax.set_title(f"Argo Float {platform_number} • Cycle {cycle_number}\nVertical Depth Profile", 
                 fontsize=12, fontweight='bold', pad=15, family='sans-serif')
    ax.set_xlabel(unit_map[param_col], fontsize=10, fontweight='bold', labelpad=12)
    ax.set_ylabel("Depth (Pressure in decibars / meters)", fontsize=10, fontweight='bold', labelpad=12)
    
    # Invert Y-axis so depth goes downwards!
    ax.invert_yaxis()
    
    # Save chart
    file_name = f"profile_{platform_number}_cycle{cycle_number}_{param_col}.png"
    out_path = config.PLOTS_DIR / file_name
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    return out_path.resolve()

def plot_trajectory_map(platform_number):
    """
    Generates an interactive HTML map showing the full drift path of a float.
    Utilizes high-res Esri satellite imagery and SaaS-styled dashed lines.
    """
    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = """
        SELECT cycle_number, latitude, longitude, juld
        FROM profiles
        WHERE platform_number = ? AND latitude IS NOT NULL AND longitude IS NOT NULL
        ORDER BY cycle_number ASC;
        """
        cur.execute(query, (platform_number,))
        rows = cur.fetchall()
    finally:
        # FIX (#2): Always close, even if the query raises.
        if conn:
            conn.close()
    
    if not rows:
        raise ValueError(f"No geographic profiles found for float {platform_number}")
        
    latest_lat, latest_lon = rows[-1][1], rows[-1][2]
    
    # 1. Use Esri World Imagery for that rich, photorealistic satellite look
    m = folium.Map(
        location=[latest_lat, latest_lon], 
        zoom_start=6, 
        tiles='https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}',
        attr='Esri World Imagery'
    )
    
    # 2. Draw path line in dashed white
    points = [[r[1], r[2]] for r in rows]
    folium.PolyLine(
        points, 
        color='#ffffff', 
        weight=2.5, 
        opacity=0.8, 
        dash_array='8, 8', # Creates the dashed effect
        tooltip=f"Float {platform_number} Track"
    ).add_to(m)
    
    # 3. Add Markers
    for idx, (cycle_num, lat, lon, juld_str) in enumerate(rows):
        is_latest = (idx == len(rows) - 1)
        date_short = juld_str[:10] if juld_str else "Unknown Date"
        
        # Sleek dark-mode popup box
        popup_html = f"""
        <div style="font-family: 'Outfit', Arial, sans-serif; font-size: 11px; color:#E2E8F0; background:#0B0F19; border-radius:4px; padding:5px;">
            <b style="color:#35D07F;">Float {platform_number}</b><br>
            <b>Cycle:</b> {cycle_num}<br>
            <b>Date:</b> {date_short}<br>
            <b>Coords:</b> {lat:.3f}°N, {lon:.3f}°E
        </div>
        """
        
        iframe = folium.IFrame(html=popup_html, width=150, height=80)
        popup = folium.Popup(iframe, max_width=200)
        
        if is_latest:
            # Glowing white & neon green marker for current coordinate
            folium.CircleMarker(
                location=[lat, lon],
                radius=7,
                color='#35D07F', # Neon green outline
                fill=True,
                fill_color='#ffffff', # White center
                fill_opacity=1,
                weight=3.5,
                popup=popup,
                tooltip=f"Latest Position (Cycle {cycle_num})"
            ).add_to(m)
        else:
            # Subtle white dots for history points
            folium.CircleMarker(
                location=[lat, lon],
                radius=3,
                color='#ffffff',
                fill=True,
                fill_color='#ffffff',
                fill_opacity=0.4,
                weight=1,
                popup=popup,
                tooltip=f"Cycle {cycle_num}"
            ).add_to(m)
            
    # Save Map
    file_name = f"trajectory_{platform_number}.html"
    out_path = config.MAPS_DIR / file_name
    m.save(str(out_path))
    
    return out_path.resolve()

def plot_time_series(platform_number, parameter='temperature'):
    """
    Plots surface measurements (depth < 10m) over time in dark mode.
    """
    # FIX (#3): Same safe whitelist pattern as plot_depth_profile.
    SAFE_PARAM_COLS = {
        'temperature': 'temperature',
        'salinity':    'salinity',
    }
    param_col = parameter.lower()
    if param_col not in SAFE_PARAM_COLS:
        raise ValueError(f"Time series only supported for temperature or salinity. Got: {parameter}")
    safe_col = SAFE_PARAM_COLS[param_col]

    conn = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        query = f"""
        SELECT p.juld, AVG(m.{safe_col})
        FROM measurements m
        JOIN profiles p ON m.profile_id = p.profile_id
        WHERE p.platform_number = ? AND m.pressure < 10 AND m.{safe_col} IS NOT NULL
        GROUP BY p.profile_id
        ORDER BY p.juld ASC;
        """
        cur.execute(query, (platform_number,))
        rows = cur.fetchall()
    finally:
        # FIX (#2): Always close, even if the query raises.
        if conn:
            conn.close()
    
    if not rows:
        raise ValueError(f"No surface observations found for float {platform_number}")
        
    import pandas as pd
    dates = [pd.to_datetime(r[0]) for r in rows]
    vals = [r[1] for r in rows]
    
    # 3. Apply Spline to Time Series if enough points exist
    if len(dates) > 3:
        dates_numeric = mdates.date2num(dates)
        dates_smooth_numeric = np.linspace(min(dates_numeric), max(dates_numeric), 200)
        dates_smooth = mdates.num2date(dates_smooth_numeric)
        try:
            spline = make_interp_spline(dates_numeric, vals, k=3)
            vals_smooth = spline(dates_smooth_numeric)
        except Exception:
            dates_smooth = dates
            vals_smooth = vals
    else:
        dates_smooth = dates
        vals_smooth = vals

    # Plot
    fig, ax = plt.subplots(figsize=(10, 5))
    
    color_map = {'temperature': '#FF5A36', 'salinity': '#00D2FF'}
    unit_map = {'temperature': 'Sea Surface Temperature (°C)', 'salinity': 'Sea Surface Salinity (psu)'}
    color = color_map[param_col]
    
    # Smooth line + shadow
    ax.plot(dates_smooth, vals_smooth, color=color, linewidth=2.5, label='Smooth Curve')
    ax.fill_between(dates_smooth, vals_smooth, color=color, alpha=0.12)
    ax.scatter(dates, vals, color=color, s=25, alpha=0.8, edgecolors='#ffffff', linewidths=0.5, label='Actual Surface Readings')
    
    # Apply theme
    apply_dark_theme(fig, ax)
    
    # Date formatting
    ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=3))
    fig.autofmt_xdate()
    
    ax.set_title(f"Argo Float {platform_number} • Sea Surface {parameter.title()} Timeline", 
                 fontsize=12, fontweight='bold', pad=15, family='sans-serif')
    ax.set_ylabel(unit_map[param_col], fontsize=10, fontweight='bold', labelpad=12)
    ax.set_xlabel("Observation Date", fontsize=10, fontweight='bold', labelpad=12)
    
    file_name = f"timeseries_{platform_number}_{param_col}.png"
    out_path = config.PLOTS_DIR / file_name
    plt.tight_layout()
    plt.savefig(out_path, dpi=150, facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    return out_path.resolve()
