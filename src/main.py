import argparse
import logging
from dotenv import load_dotenv
import os
from database.db import DatabaseManager
from sensors.dht11 import DHT11Sensor
from sensors.camera import capture_photo_and_save
from services.discord_bot import send_discord_photo_report

# Load environment variables from .env file
load_dotenv()

DISCORD_PHOTO_WEBHOOK_URL = os.getenv('DISCORD_PHOTO_WEBHOOK_URL')

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", action="store_true", help="Capture webcam photo and send Discord update")
    args = parser.parse_args()

    db = DatabaseManager("data/plant_monitor.db")

    # Read sensor if not taking photo
    if not args.photo:
        sensor = DHT11Sensor(pin_number=4)

        # Read Hygrometer Data
        sensor_data = sensor.read() or {}
        temp_c = sensor_data.get("temperature_c")
        temp_f = sensor_data.get("temperature_f")
        humidity = sensor_data.get("humidity")
        vpd = sensor_data.get("vpd_kpa")

        reading_id = db.insert_reading(
            temp_c=temp_c,
            temp_f=temp_f,
            humidity=humidity,
            vpd_kpa=vpd
        )
        logging.info(f"Logged reading ID {reading_id} to database.")

    # Conditionally Capture Photo
    image_path = None
    if args.photo:
        image_path = capture_photo_and_save()
        photo_id = db.insert_photo(file_path=image_path)
        logging.info(f"Logged photo ID {photo_id} to database.")

        summaries = db.get_daily_timelapse_summary(limit=1)
        if not summaries:
            print("No daily data found.")
            return

        latest_summary = summaries[0]

        # Send Discord photo report
        if DISCORD_PHOTO_WEBHOOK_URL:
            send_discord_photo_report(DISCORD_PHOTO_WEBHOOK_URL, latest_summary, image_path)
        else:
            logging.error("DISCORD_PHOTO_WEBHOOK_URL is not set in .env file.")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()