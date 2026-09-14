import os
import json
import requests
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger(__name__)

def send_discord_photo_report(
    webhook_url: str, 
    daily_summary: Dict[str, Any], 
    photo_path: Optional[str] = None
) -> None:
    if not webhook_url:
        logger.warning("⚠️ Missing Webhook URL")
        return

    # Extract metrics safely from dictionary or database row
    avg_temp_f = daily_summary.get("avg_temp_f")
    avg_humidity = daily_summary.get("avg_humidity")
    avg_vpd = daily_summary.get("avg_vpd_kpa")

    # Format output text for metrics
    temp_str = f"{avg_temp_f:.1f} °F" if avg_temp_f is not None else "N/A"
    hum_str = f"{avg_humidity:.1f}%" if avg_humidity is not None else "N/A"
    vpd_str = f"{avg_vpd:.2f} kPa" if avg_vpd is not None else "N/A"

    # 1. Initialize embed dictionary with fields
    embed = {
        "color": 3066993,  # Green color code
        "fields": [
            {"name": "Avg Temp", "value": temp_str, "inline": True},
            {"name": "Avg Humidity", "value": hum_str, "inline": True},
            {"name": "Avg VPD", "value": vpd_str, "inline": True},
        ]
    }

    files = {}

    # 2. Attach image file if present and add "image" key to embed
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
                data={"payload_json": json.dumps(payload)}, 
                files=files, 
                timeout=10
            )
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)

        if response.ok:
            logger.info("Successfully posted daily summary to Discord")
        else:
            logger.error(f"Discord error: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"Failed to reach Discord webhook: {e}")
    finally:
        if "file" in files:
            files["file"][1].close()

def send_discord_hourly_report(
    webhook_url: str, 
    hourly_summary: Dict[str, Any]
) -> None:
    if not webhook_url:
        logger.warning("⚠️ Missing Webhook URL")
        return

    # Extract metrics safely from dictionary or database row
    temp_f = hourly_summary.get("temperature_f")
    humidity = hourly_summary.get("humidity")
    vpd = hourly_summary.get("vpd_kpa")

    # Format output text for metrics
    temp_str = f"{temp_f:.1f} °F" if temp_f is not None else "N/A"
    hum_str = f"{humidity:.1f}%" if humidity is not None else "N/A"
    vpd_str = f"{vpd:.2f} kPa" if vpd is not None else "N/A"

    # 1. Initialize embed dictionary with fields
    embed = {
        "color": 3066993,  # Green color code
        "fields": [
            {"name": "Temp", "value": temp_str, "inline": True},
            {"name": "Humidity", "value": hum_str, "inline": True},
            {"name": "VPD", "value": vpd_str, "inline": True},
        ]
    }

    payload = {
        "embeds": [embed]
    }

    try:
        response = requests.post(webhook_url, json=payload, timeout=10)

        if response.ok:
            logger.info("Successfully posted daily summary to Discord")
        else:
            logger.error(f"Discord error: {response.status_code} - {response.text}")
    except requests.RequestException as e:
        logger.error(f"Failed to reach Discord webhook: {e}")
    finally:
        return