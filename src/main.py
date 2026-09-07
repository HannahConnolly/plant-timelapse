import argparse

parser = argparse.ArgumentParser()
parser.add_argument("--photo", action="store_true", help="Capture webcam photo")
args = parser.parse_args()

# Always read DHT11 and log to DB
reading = read_dht11()
save_to_sqlite(reading)

# Conditionally take photo and send Discord update
if args.photo:
    image = capture_webcam_frame()
    send_discord_report(reading, image)