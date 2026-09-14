import argparse
import logging
import os
import sys
from pathlib import Path
from dotenv import load_dotenv

try:
    from .database.db import DatabaseManager
    from .sensors.dht11 import DHT11Sensor
    from .sensors.camera import capture_photo_and_save
    from .services.discord_bot import send_discord_photo_report, send_discord_hourly_report
except ImportError:
    from database.db import DatabaseManager
    from sensors.dht11 import DHT11Sensor
    from sensors.camera import capture_photo_and_save
    from services.discord_bot import send_discord_photo_report, send_discord_hourly_report

# Dynamic resolution for project directory & environment loading
PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

# Environment configurations
DISCORD_PHOTO_WEBHOOK_URL = os.getenv("DISCORD_PHOTO_WEBHOOK_URL")
DISCORD_SENSOR_WEBHOOK_URL = os.getenv("DISCORD_SENSOR_WEBHOOK_URL")
DB_PATH = PROJECT_ROOT / "data" / "plant_monitor.db"


def process_sensor_reading(db: DatabaseManager) -> None:
    """Reads DHT11 sensor metrics, records them in DB, and dispatches Discord update."""
    sensor = DHT11Sensor(pin_number=4)
    sensor_data = sensor.read() or {}

    reading_id = db.insert_reading(
        temp_c=sensor_data.get("temperature_c"),
        temp_f=sensor_data.get("temperature_f"),
        humidity=sensor_data.get("humidity"),
        vpd_kpa=sensor_data.get("vpd_kpa")
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
        todays_weather = daily_summary[0]
        send_discord_photo_report(
            webhook_url=DISCORD_PHOTO_WEBHOOK_URL, 
            daily_summary=todays_weather, 
            photo_path=photo_path
        )

def main() -> None:
    parser = argparse.ArgumentParser(description="Plant Monitoring CLI Execution")
    parser.add_argument(
        "--photo", 
        action="store_true", 
        help="Capture webcam photo and send Discord update"
    )
    args = parser.parse_args()

    db = DatabaseManager(str(DB_PATH))

    if args.photo:
        process_photo_report(db)
    else:
        process_sensor_reading(db)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout)
        ]
    )
    main()