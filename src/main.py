import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    from src.database.db import DatabaseManager
    from src.sensors.camera import capture_photo_and_save
    from src.sensors.dht11 import DHT11Sensor
    from src.services.animation import collect_photos, create_growth_animation
    from src.services.discord_bot import (
        post_gemini_report_to_discord,
        send_discord_animation_report,
        send_discord_hourly_report,
        send_discord_photo_report,
    )
    from src.services.genai import send_gemini_report
except ImportError:
    from database.db import DatabaseManager
    from sensors.camera import capture_photo_and_save
    from sensors.dht11 import DHT11Sensor
    from services.animation import collect_photos, create_growth_animation
    from services.discord_bot import (
        post_gemini_report_to_discord,
        send_discord_animation_report,
        send_discord_hourly_report,
        send_discord_photo_report,
    )
    from services.genai import send_gemini_report

# Dynamic resolution for project directory & environment loading
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Environment configurations
DISCORD_PHOTO_WEBHOOK_URL = os.getenv("DISCORD_PHOTO_WEBHOOK_URL")
DISCORD_SENSOR_WEBHOOK_URL = os.getenv("DISCORD_SENSOR_WEBHOOK_URL")
DISCORD_GEMINI_WEBHOOK_URL = os.getenv("DISCORD_GEMINI_WEBHOOK_URL")
DISCORD_ANIMATION_WEBHOOK_URL = (
    os.getenv("DISCORD_ANIMATION_WEBHOOK_URL") or DISCORD_PHOTO_WEBHOOK_URL
)
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
DB_PATH = PROJECT_ROOT / "data" / "plant_monitor.db"
PHOTOS_DIR = PROJECT_ROOT / "data" / "photos"
ANIMATIONS_DIR = PROJECT_ROOT / "data" / "animations"


def process_sensor_reading(db: DatabaseManager) -> None:
    """Reads DHT11 sensor metrics, records them in DB, and dispatches Discord update."""
    sensor = DHT11Sensor(pin_number=4)
    sensor_data = sensor.read() or {}

    reading_id = db.insert_reading(
        temp_c=sensor_data.get("temperature_c"),
        temp_f=sensor_data.get("temperature_f"),
        humidity=sensor_data.get("humidity"),
        vpd_kpa=sensor_data.get("vpd_kpa"),
    )
    logging.info(f"Logged reading ID {reading_id} to database.")

    hourly_report = db.get_recent_readings(limit=1)
    if not hourly_report:
        logging.error("No recent sensor data found in database.")
        return

    if not DISCORD_SENSOR_WEBHOOK_URL:
        logging.error("DISCORD_SENSOR_WEBHOOK_URL is not set.")
        return

    send_discord_hourly_report(DISCORD_SENSOR_WEBHOOK_URL, hourly_report[0])


def process_photo_report(db: DatabaseManager) -> None:
    """Captures camera image and sends photo report with environmental averages via Discord."""
    if not DISCORD_PHOTO_WEBHOOK_URL:
        logging.error("DISCORD_PHOTO_WEBHOOK_URL is not set.")
        return

    photo_path = capture_photo_and_save()
    if not photo_path:
        logging.error("Failed to capture photo.")
        return

    # Fetch daily metrics summary to pass along with the photo report
    daily_summary = db.get_daily_timelapse_summary()

    print(daily_summary)
    if daily_summary:
        todays_climate = daily_summary[0]
        send_discord_photo_report(
            webhook_url=DISCORD_PHOTO_WEBHOOK_URL,
            daily_summary=todays_climate,
            photo_path=photo_path,
        )


def gemini_report(db: DatabaseManager):
    """Sends the aggregated reading data and photo to the Google Gemini API."""
    if not GEMINI_API_KEY:
        logging.error("GEMINI_API_KEY is not set.")
        return None

    daily_summary = db.get_daily_timelapse_summary()
    if not daily_summary:
        logging.error("No daily summary found in database.")
        return None

    response = send_gemini_report(daily_summary[0], GEMINI_API_KEY)
    print(response)
    return response


def process_growth_animation() -> None:
    """Builds a GIF from every daily photo so far and posts it to Discord."""
    if not DISCORD_ANIMATION_WEBHOOK_URL:
        logging.error("DISCORD_ANIMATION_WEBHOOK_URL (or DISCORD_PHOTO_WEBHOOK_URL) is not set.")
        return

    photos = collect_photos(PHOTOS_DIR)
    if len(photos) < 2:
        logging.error(f"Need at least 2 photos to animate; found {len(photos)}.")
        return

    start_date, end_date = photos[0][0], photos[-1][0]
    output_path = ANIMATIONS_DIR / f"growth_{start_date.isoformat()}_to_{end_date.isoformat()}.gif"
    animation_path = create_growth_animation(photos, output_path)
    if not animation_path:
        return

    title = f"Growth so far: {start_date:%b %d} – {end_date:%b %d}"
    send_discord_animation_report(
        DISCORD_ANIMATION_WEBHOOK_URL, animation_path, title, frame_count=len(photos)
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Plant Monitoring CLI Execution")
    parser.add_argument(
        "--photo",
        action="store_true",
        help="Capture webcam photo and send Discord update",
    )
    parser.add_argument(
        "--ai",
        action="store_true",
        help="Send aggregated reading data and photo to Google Gemini API",
    )
    parser.add_argument(
        "--animation",
        action="store_true",
        help="Build a growth animation from all daily photos and send it to Discord",
    )
    args = parser.parse_args()

    db = DatabaseManager(str(DB_PATH))

    if args.photo:
        process_photo_report(db)
    elif args.animation:
        process_growth_animation()
    elif args.ai:
        response = gemini_report(db)
        if response is not None:
            post_gemini_report_to_discord(DISCORD_GEMINI_WEBHOOK_URL, response)
        else:
            logging.error("Gemini report generation failed; Discord update skipped.")
    else:
        process_sensor_reading(db)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    main()
