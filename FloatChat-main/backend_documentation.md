# FloatChat — Backend Architecture & Process Documentation

This document covers the file structure, internal processes, and end-to-end workflows of the FloatChat backend data conversion pipeline and AI SQL/Visualization Agent.

---

## 📁 1. The Backend File Layout

All backend code and data files reside in the `backend/` directory of the workspace:

```
backend/
├── data/
│   ├── floatchat.db        # The active SQLite database file
│   ├── manifest.json       # Manifest tracking downloaded files to prevent duplicates
│   └── raw/incois/...      # Raw downloaded .nc (NetCDF) profile files
├── static/
│   ├── plots/              # Saved PNG charts (Depth profiles, Surface timelines)
│   ├── maps/               # Saved HTML maps (Leaflet trajectory tracks)
│   ├── index.html          # Web dashboard layout
│   ├── style.css           # Glassmorphic dark-theme stylesheet
│   └── app.js              # Frontend dashboard JS controller
├── .env                    # Secure environment variables (holds GEMINI_API_KEY)
├── .gitignore              # Ignores db files, raw Nc data, logs, and API keys from Git
├── schema.sql              # Database DDL structure
├── config.py               # Global configurations & pipeline filters
├── ingest.py               # Downloads and filters files from GDAC Ifremer servers
├── parse.py                # Extracts variables from binary NetCDF files using xarray
├── qc_filter.py            # Quality Control filter (retains flags 1 and 2)
├── load.py                 # SQLite transaction loader & database auto-initializer
├── visualizer.py           # Matplotlib (spline curves) & Folium mapping module
├── sql_agent.py            # AI SQL translation & token-saving guardrails engine
├── run_pipeline.py         # Master pipeline orchestrator script
└── app.py                  # Flask Web API server
```

---

## ⚙️ 2. File-by-File Processes

### 🗄️ Database & Configuration

* **`schema.sql`**:
  * **Process**: Defines the relational structure for storing Argo float profiles. It sets up three tables:
    * `floats`: Base metadata about each physical robotic float (ID, type).
    * `profiles`: Dive-level metadata (cycle number, timestamp, coordinate lat/lon).
    * `measurements`: Deep time-series measurements (pressure/depth, temp, salinity, oxygen, chlorophyll) along with their respective QC flags.
  * **Indexing**: Creates composite indexes on coordinate columns (`latitude`, `longitude`) to speed up spatial bounding box queries and on `profile_id` for instant measurement joining.

* **`config.py`**:
  * **Process**: Centralizes all configuration settings, directories, and data limits.
  * **Active Filters**:
    * `FILTER_DACS = ["incois"]`: Restricts downloads to Indian floats managed by INCOIS.
    * `FILTER_BBOX = [50.0, 0.0, 95.0, 25.0]`: Restricts data geographically to the Arabian Sea & Bay of Bengal.
    * `FILTER_MIN_YEAR = 2021`: Restricts profiles to the last 5 years of observations.
    * `LIMIT_FILES = 400`: Safe boundary to cap the total downloaded files during execution.
    * `ACCEPTED_QC_FLAGS = [1, 2]`: Keeps only "Good" or "Probably Good" data.

---

### 🌊 Ingestion & Extraction Pipeline

* **`ingest.py`**:
  * **Process**: Downloads the global profile registry index (`ar_index_global_prof.txt.gz`) from the Ifremer mirror. It configures standard Python HTTPS contexts to bypass Windows-specific SSL root certificate validation errors. It loops over the registry, filters out records not matching our DAC, BBOX, or Year constraints, checks `manifest.json` to prevent downloading duplicates, and downloads the raw NetCDF files locally.

* **`parse.py`**:
  * **Process**: Opens the binary NetCDF (`.nc`) files using `xarray` and `netCDF4` or `h5netcdf` engines. It decodes byte arrays, strips metadata strings, converts Julian Dates to standard Python datetimes, and flattens the multi-dimensional pressure levels (depths) into a list of row dictionaries.

* **`qc_filter.py`**:
  * **Process**: Cleans the data according to official Argo quality flags:
    * If `pressure_qc` is not `1` or `2`, the entire depth row is skipped.
    * If a parameter's specific QC (e.g. `temperature_qc` or `salinity_qc`) is invalid, that specific measurement value is set to `None` in Python (translating to a database `NULL`).
    * If a depth level ends up with zero valid variables, the row is discarded to save database storage.

* **`load.py`**:
  * **Process**: Opens an SQLite connection. It queries `sqlite_master` to check for the presence of tables; if absent, it automatically runs `schema.sql` (auto-initialization). It inserts the float and profile, wipes out any duplicate measurements for that profile cycle (to cleanly overwrite real-time data with corrected delayed-mode data), and uses `executemany` for high-speed database load.

---

### 🧠 AI SQL & Visualization Engines

* **`visualizer.py`**:
  * **Process**: Reads SQLite records and converts them to high-fidelity visual assets:
    * **Depth Profiles**: Queries the vertical measurements, sorts by pressure, and uses **cubic spline interpolation (`scipy.interpolate.make_interp_spline`)** to smooth zig-zag measurements into flowing curves. It renders them on a dark background (`#0B0F19`) with translucent glow shadows under the curve.
    * **Trajectory Maps**: Queries coordinate lists chronologically and generates an interactive Leaflet map using **`folium` (Dark Matter theme)**, connecting coordinates with glowing cyan lines and marking the latest coordinate with a prominent red marker.
    * **Time Series**: Compiles surface measurements (depth < 10m) over time and plots surface transitions.

* **`sql_agent.py`**:
  * **Process**: Connects to the **`gemini-3.5-flash-lite`** API using the `google-genai` client and loads settings from `.env`.
  * **Topic Guardrail**: First, Gemini evaluates the user query. If the question is off-topic (e.g. cooking, coding, general trivia), it returns `REJECT: off-topic`. The agent intercepts this and returns a polite refusal, **saving 60%+ of your token budget** by bypassing SQLite execution and avoiding the secondary explanation LLM call.
  * **SQL Translation**: If on-topic, Gemini writes an optimized SQLite query, the agent runs it against `floatchat.db`, and passes the data rows back to Gemini to explain the results in a friendly, conversational sentence in the user's input language.

* **`run_pipeline.py`**:
  * **Process**: Master coordinator that orchestrates the ingestion loop, parses NetCDF files, filters them, connects to SQLite to perform transactional loads, and logs any individual file failures to `failed_files.log` so the process doesn't halt.

* **`app.py`**:
  * **Process**: Runs the local API server using Flask on `http://127.0.0.1:5000`. Exposes:
    * `GET /api/floats`: Retrieves lists of floats, active badges, coordinates, and cycle counts for the dashboard sidebar.
    * `POST /api/chat`: Routes natural language questions to the SQL Agent. It cleans absolute local paths `file:///` in the markdown responses into relative paths `/static/plots/...` or `/static/maps/...` to bypass browser security restrictions.

---

## 🔄 3. System Workflows

### A. The Data Ingestion Workflow (Daily / Incremental)

```
[Argo GDAC Server] ──> [ingest.py] ──(Filters: incois, BBOX, Year)──> [Raw Nc Downloads]
                                                                            │
[SQLite DB] <── [load.py] <── [qc_filter.py] <── [parse.py] <───────────────┘
```

### B. The User Query & Visualization Workflow (Real-time Chat)

```
                    [User Question]
                           │
                           ▼
                 [sql_agent.py] (Gemini 3.5 Flash Lite)
                           │
            ┌──────────────┴──────────────┐
            │ (On-Topic?)                 │ (Off-Topic?)
            ▼                             ▼
      [DB SQL Query]               [REJECT: off-topic]
            │                             │
       ┌────┴────┐                        ▼
       ▼         ▼                [Polite Refusal] (Stop)
   [SQLite DB] [visualizer.py]
       │         │
       ▼         ▼
   [Raw Data] [PNG / HTML Maps]
       │         │
       └────┬────┘
            ▼
   [Conversational Answer] ──> [Web Frontend Dashboard]
```
