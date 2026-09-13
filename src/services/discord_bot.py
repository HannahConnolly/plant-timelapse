import os
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def send_discord_photo_report(
    webhook_url: str, 
    daily_summary: Dict[str, Any], 
    photo_path: Optional[str] = None
) -> None:
    """
    Sends a daily timelapse photo report with environmental averages to Discord.
    
    :param webhook_url: Discord webhook URL
    :param daily_summary: Dict or sqlite3.Row containing daily averages:
                          e.g. {'log_date': '2026-09-13', 'avg_temp_f': 75.2, 
                                'avg_humidity': 62.4, 'avg_vpd_kpa': 1.15}
    :param photo_path: Path to the daily timelapse photo file (optional)
    """
    if not webhook_url:
        logger.warning("⚠️ Missing Webhook URL")
        return

    # Extract metrics safely from dictionary or database row
    log_date = daily_summary.get("log_date", "Today")
    avg_temp_f = daily_summary.get("avg_temp_f")
    avg_humidity = daily_summary.get("avg_humidity")
    avg_vpd = daily_summary.get("avg_vpd_kpa")

    # Format output text for metrics
    temp_str = f"{avg_temp_f:.1f} °F" if avg_temp_f is not None else "N/A"
    hum_str = f"{avg_humidity:.1f}%" if avg_humidity is not None else "N/A"
    vpd_str = f"{avg_vpd:.2f} kPa" if avg_vpd is not None else "N/A"

    # 1. Build structured Discord Embed fields for daily summary
    embed = {
        "title": f"🌱 Daily Timelapse Summary - {log_date}",
        "color": 3066993,  # Green color code
        "fields": [
            {"name": "Avg Temp", "value": temp_str, "inline": True},
            {"name": "Avg Humidity", "value": hum_str, "inline": True},
            {"name": "Avg VPD", "value": vpd_str, "inline": True},
        ]
    }

    files = {}

    # 2. Attach image file if present and reference it inside the embed
    if photo_path and os.path.exists(photo_path):
        filename = os.path.basename(photo_path)
        embed["image"] = {"url": f"attachment://{filename}"}
        files["file"] = (filename, open(photo_path, "rb"))

    payload = {
        "embeds": [embed]
    }

    try:
        # Pass JSON payload as multipart form parameter when sending files
        if files:
            response = requests.post(
                webhook_url, 
                data={"payload_json": requests.compat.json.dumps(payload)}, 
                files=files, 
                timeout=10
            )
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)

        if response.ok:
            logger.info(" Successfully posted daily summary to Discord")
        else:
            logger.error(f" Discord error: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f" Failed to reach Discord webhook: {e}")
    finally:
        if "file" in files:
            files["file"][1].close()