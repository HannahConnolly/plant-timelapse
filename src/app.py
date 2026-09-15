import os
import sys
from pathlib import Path

from flask import Flask, jsonify, render_template, send_from_directory

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.database.db import DatabaseManager
except ImportError:
    from database.db import DatabaseManager

app = Flask(__name__)
db = DatabaseManager("data/plant_monitor.db")

# Define absolute path to the data/photos directory
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
PHOTOS_DIR = os.path.join(PROJECT_ROOT, "data", "photos")


def normalize_photo_path(file_path: str) -> str:
    """Keep only the basename so we never serve a nested data/photos path."""
    if not file_path:
        return ""
    normalized = os.path.normpath(file_path.strip())
    if normalized.startswith("/"):
        normalized = normalized.lstrip("/")
    return os.path.basename(normalized)


@app.route("/")
def index():
    # Fetch latest reading for current metrics and latest photo
    latest = db.get_recent_readings(limit=1)
    current_data = latest[0] if latest else {}
    if current_data.get("file_path"):
        current_data["file_path"] = normalize_photo_path(current_data["file_path"])
    print(current_data)
    return render_template("index.html", data=current_data)


@app.route("/api/history")
def history():
    # Get recent logs for a temperature/humidity chart
    readings = db.get_recent_readings(limit=24)
    for reading in readings:
        if reading.get("file_path"):
            reading["file_path"] = normalize_photo_path(reading["file_path"])
    return jsonify(readings)


@app.route("/photos/<path:filename>")
def serve_photo(filename):
    safe_name = normalize_photo_path(filename)
    return send_from_directory(PHOTOS_DIR, safe_name)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
