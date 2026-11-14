# app.py
# Flask server to expose FloatChat APIs and serve the frontend dashboard

import re
import sqlite3
from flask import Flask, request, jsonify, send_from_directory
import config
import sql_agent

app = Flask(__name__, static_folder="static", static_url_path="/static")

def get_ro_db_connection():
    """Open a read-only SQLite connection so the API endpoint can never modify the DB."""
    db_uri = f"file:{config.DB_PATH.as_posix()}?mode=ro"
    return sqlite3.connect(db_uri, uri=True)

@app.route("/")
def index():
    """Serve the main frontend dashboard."""
    return send_from_directory("static", "index.html")

@app.route("/api/floats", methods=["GET"])
def get_floats():
    """Retrieves all floats in the database along with cycle counts and last known positions."""
    conn = None
    try:
        conn = get_ro_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT platform_number, float_type, deployment_date FROM floats;")
        floats_raw = cur.fetchall()

        floats_list = []
        for f in floats_raw:
            plat_num, fl_type, dep_date = f[0], f[1], f[2]

            # Total cycle count
            cur.execute(
                "SELECT COUNT(*) FROM profiles WHERE platform_number = ?;",
                (plat_num,)
            )
            cycles_count = cur.fetchone()[0] or 0

            # FIX (#6): Use ORDER BY juld DESC LIMIT 1 to get the *actual* latest row.
            # The old SELECT COUNT(*), MAX(juld), latitude, longitude query had SQLite
            # aggregate ambiguity — latitude/longitude came from an arbitrary row, NOT
            # the one with MAX(juld).
            cur.execute("""
                SELECT juld, latitude, longitude
                FROM profiles
                WHERE platform_number = ?
                  AND latitude IS NOT NULL AND longitude IS NOT NULL
                ORDER BY juld DESC
                LIMIT 1;
            """, (plat_num,))
            latest_row = cur.fetchone()
            latest_date = (latest_row[0][:10] if latest_row else dep_date)
            latest_lat  = latest_row[1] if latest_row else None
            latest_lon  = latest_row[2] if latest_row else None

            floats_list.append({
                "platform_number": plat_num,
                "float_type": fl_type.upper() if fl_type else "CORE",
                "deployment_date": dep_date,
                "cycles_count": cycles_count,
                "latest_date": latest_date,
                "latest_lat": latest_lat,
                "latest_lon": latest_lon,
                "status": "ACTIVE" if cycles_count > 0 else "INACTIVE"
            })

        return jsonify(floats_list)

    except Exception as e:
        return jsonify({"error": f"Failed to retrieve floats: {e}"}), 500
    finally:
        # FIX (#1): Always close the connection, even if an exception was raised.
        if conn:
            conn.close()

@app.route("/api/chat", methods=["POST"])
def chat():
    """Handles natural language questions, executing SQL or Plotting and returning clean results."""
    data = request.json
    if not data or "message" not in data:
        return jsonify({"error": "Missing 'message' parameter"}), 400
        
    user_message = data["message"]

    if not isinstance(user_message, str) or not user_message.strip():
        return jsonify({"error": "Message must be a non-empty string"}), 400

    try:
        # Call the core SQL & Visualization agent
        agent_response = sql_agent.ask_agent(user_message)
        
        # Convert any absolute local file paths in the markdown into relative web server paths.
        # FIX (#14): Normalize backslashes to forward slashes first so the regex
        # works on Windows paths like file:///C:\Users\...\backend\static as well.
        agent_response_normalized = agent_response.replace("\\", "/")
        cleaned_response = re.sub(
            r'file:///+.*?/backend/static',
            '/static',
            agent_response_normalized,
            flags=re.IGNORECASE
        )
        
        # Check if response contains an embedded plot image path or map iframe path
        # to help the frontend render them nicely
        img_match = re.search(r'!\[.*?\]\((/static/plots/.*?)\)', cleaned_response)
        map_match = re.search(r'\[.*?\]\((/static/maps/.*?)\)', cleaned_response)
        
        plot_url = img_match.group(1) if img_match else None
        map_url = map_match.group(1) if map_match else None
        
        return jsonify({
            "response": cleaned_response,
            "plot_url": plot_url,
            "map_url": map_url
        })
        
    except Exception as e:
        return jsonify({"error": f"Agent failed: {e}"}), 500

if __name__ == "__main__":
    print("Starting FloatChat local web server on http://127.0.0.1:5000")
    app.run(host="127.0.0.1", port=5000, debug=False)
