import json
import logging
import os
import re
from pathlib import Path
from typing import Any

import requests

logger = logging.getLogger(__name__)


def send_discord_photo_report(
    webhook_url: str, daily_summary: dict[str, Any], photo_path: str | None = None
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
        ],
    }

    files = {}

    # 2. Attach image file if present and add "image" key to embed
    if photo_path and os.path.exists(photo_path):
        filename = os.path.basename(photo_path)
        embed["image"] = {"url": f"attachment://{filename}"}
        files["file"] = (filename, open(photo_path, "rb"))

    payload = {"embeds": [embed]}

    try:
        # Pass JSON payload as multipart form parameter when sending files
        if files:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=10,
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
    webhook_url: str, hourly_summary: dict[str, Any]
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
        ],
    }

    payload = {"embeds": [embed]}

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


def _extract_json_payload(raw_text: Any) -> dict[str, Any] | None:
    """Normalize Gemini outputs that may be wrapped in markdown code fences."""
    if raw_text is None:
        return None

    text = str(raw_text).strip()
    if not text:
        return None

    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\s*```\s*$", "", text, flags=re.IGNORECASE)

    start = text.find("{")
    end = text.rfind("}")
    if 0 <= start < end:
        text = text[start : end + 1]

    try:
        parsed = json.loads(text)
        return parsed if isinstance(parsed, dict) else None
    except (json.JSONDecodeError, TypeError):
        return None


def post_gemini_report_to_discord(
    webhook_url: str | None = None, gemini_response: str | dict[str, Any] | Any = None
) -> bool:
    """
    Parses a Gemini response payload (string JSON or response object)
    and posts a formatted Embed report to Discord via Webhook.
    """
    if not webhook_url:
        logger.error("Discord Webhook URL is missing or not provided.")
        return False

    # Extract JSON string from supported Gemini response formats
    if isinstance(gemini_response, str):
        raw_json = gemini_response
    elif isinstance(gemini_response, dict):
        raw_json = json.dumps(gemini_response)
    elif hasattr(gemini_response, "text"):
        raw_json = str(gemini_response.text or "")
    elif hasattr(gemini_response, "candidates"):
        candidates = gemini_response.candidates or []
        for candidate in candidates:
            content = getattr(candidate, "content", None)
            if not content:
                continue
            parts = getattr(content, "parts", None) or []
            for part in parts:
                part_text = getattr(part, "text", None)
                if part_text:
                    raw_json = str(part_text)
                    break
        raw_json = str(gemini_response)
    else:
        raw_json = str(gemini_response)

    if not raw_json:
        raw_json = str(getattr(gemini_response, "model_dump_json", lambda: "")() or "")

    data = _extract_json_payload(raw_json)
    if data is None:
        logger.error(f"Failed to parse Gemini JSON output: {raw_json[:200]}")
        return False

    # Extract dynamic sections from the structured JSON output
    visual = data.get("visual_assessment", {})
    climate = data.get("climate_analysis", {})
    recommendations = data.get("recommendations", [])

    # Format recommendations into markdown bullet points
    if isinstance(recommendations, list) and recommendations:
        rec_text = "\n".join([f"• {rec}" for rec in recommendations])
    else:
        rec_text = "No immediate adjustments required."

    # Construct styled Discord Embed structure
    embed = {
        "title": "🌿 Automated Plant Health Assessment",
        "color": 3066993,  # Emerald Green
        "fields": [
            {
                "name": "👁️ Visual Assessment",
                "value": (
                    f"**Health:** {visual.get('overall_health', 'N/A')}\n\n"
                    f"**Posture:** {visual.get('leaf_posture', 'N/A')}\n\n"
                    f"**Signs of Stress:** {visual.get('signs_of_stress', 'N/A')}"
                ),
                "inline": False,
            },
            {
                "name": "🌡️ Climate Analysis",
                "value": (
                    f"**Temperature:** {climate.get('temperature', 'N/A')}\n\n"
                    f"**VPD:** {climate.get('vpd', 'N/A')}"
                ),
                "inline": False,
            },
            {"name": "📋 Recommendations", "value": rec_text, "inline": False},
        ],
        "footer": {"text": "Gemini AI Plant Monitor • Automated System"},
    }

    files = {}
    photo_file_handle = None

    # Attach camera image if available and add reference to the Embed frame
    # Locate the latest image in the photos directory safely
    photos_dir = Path("data/photos")
    if not photos_dir.exists() or not photos_dir.is_dir():
        logging.error(f"Photos directory does not exist: {photos_dir.resolve()}")
        return False

    image_files = list(photos_dir.glob("*.jpg")) + list(photos_dir.glob("*.png"))
    if not image_files:
        logging.error("No image files (.jpg, .png) found in the photos directory.")
        return False
    latest_image: Path | None = None

    try:
        latest_image = max(image_files, key=lambda p: p.stat().st_mtime)
        with latest_image.open("rb") as f:
            image_bytes = f.read()
    except (OSError, PermissionError) as e:
        logging.error(f"Failed to read image file '{latest_image or '<unknown>'}': {e}")
        return False

    payload = {"embeds": [embed]}

    try:
        # Send request as multipart/form-data when transmitting image files
        if files:
            response = requests.post(
                webhook_url,
                data={"payload_json": json.dumps(payload)},
                files=files,
                timeout=10,
            )
        else:
            response = requests.post(webhook_url, json=payload, timeout=10)

        if response.ok:
            logger.info("Successfully posted Gemini analysis embed to Discord.")
            return True
        else:
            logger.error(
                f"Discord returned an error: {response.status_code} - {response.text}"
            )
            return False

    except requests.RequestException as e:
        logger.error(f"Failed to deliver request to Discord webhook: {e}")
        return False

    finally:
        if photo_file_handle:
            photo_file_handle.close()
