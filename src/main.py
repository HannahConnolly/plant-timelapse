import argparse
import logging
from database.db import DatabaseManager
from sensors.dht11 import DHT11Sensor
# from sensors.camera import Camera
# from services.discord_bot import send_discord_report

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--photo", action="store_true", help="Capture webcam photo and send Discord update")
    args = parser.parse_args()

    db = DatabaseManager("data/plant_monitor.db")
    sensor = DHT11Sensor(pin_number=4)

    # 1. Read Hygrometer Data
    sensor_data = sensor.read() or {}
    temp_c = sensor_data.get("temperature_c")
    temp_f = sensor_data.get("temperature_f")
    humidity = sensor_data.get("humidity")
    vpd = sensor_data.get("vpd_kpa")

    # 2. Conditionally Capture Photo
    image_path = None
    if args.photo:
        # TODO
        # image_path = capture_photo()
        pass

    # 3. Log Reading to SQLite
    reading_id = db.insert_reading(
        temp_c=temp_c,
        temp_f=temp_f,
        humidity=humidity,
        vpd_kpa=vpd,
        image_path=image_path
    )
    logging.info(f"Logged reading ID {reading_id} to database.")

    # 4. Conditionally Dispatch Discord Notification
    if args.photo:
        # TODO
        # send_discord_report(sensor_data, image_path)
        pass

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    main()