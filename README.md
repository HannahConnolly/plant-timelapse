# Plant Timelapse & Environmental Monitor

A Raspberry Pi plant-monitoring system that reads a DHT11 sensor, captures webcam photos, stores environmental history in SQLite, serves a local dashboard, and publishes reports to Discord. An optional Google Gemini integration analyzes the latest plant photo alongside the daily climate summary.

## Features

- DHT11 temperature and humidity readings on GPIO 4.
- Vapor Pressure Deficit (VPD) calculation in kPa.
- Webcam capture saved as dated images under `data/photos/`.
- SQLite storage for readings and photos, with a daily averages view.
- Flask dashboard with the latest reading and photo.
- JSON history endpoint at `/api/history` for the latest 24 readings.
- Separate Discord webhook reports for sensor readings, photo summaries, and Gemini assessments.
- Optional Gemini 2.5 Flash analysis with structured visual assessment, climate analysis, and recommendations.
- Retry handling for transient DHT11 read failures and hardware-library-free test execution.

## Hardware

- Raspberry Pi running Raspberry Pi OS
- DHT11 temperature and humidity sensor
- USB webcam
- Jumper wires

### DHT11 wiring

| DHT11 pin | Raspberry Pi |
| --- | --- |
| VCC | 3.3V (physical pin 1) or 5V (physical pin 2) |
| DATA | GPIO 4 (physical pin 7) |
| GND | Ground (physical pin 6) |

## Setup

From the project root:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
```

Edit `.env` with the credentials and webhook URLs you intend to use. Never commit `.env`.

```dotenv
GEMINI_API_KEY="your-gemini-api-key"
DISCORD_PHOTO_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_SENSOR_WEBHOOK_URL="https://discord.com/api/webhooks/..."
DISCORD_GEMINI_WEBHOOK_URL="https://discord.com/api/webhooks/..."
```

The database is created automatically at `data/plant_monitor.db`. The photo directory is created automatically when a capture is made.

## Running the application

`src.main` is the command-line entry point. With no flag, it reads the DHT11, stores the reading, and sends the latest sensor report to Discord:

```bash
python -m src.main
```

Capture a webcam image and send a daily environmental summary to Discord:

```bash
python -m src.main --photo
```

Send the daily summary and latest image to Gemini, then publish the structured assessment to Discord:

```bash
python -m src.main --ai
```

Run the local Flask dashboard on port 5000:

```bash
python -m src.app
```

Open `http://<raspberry-pi-ip>:5000/` in a browser. The dashboard also exposes:

- `GET /api/history` - latest 24 sensor readings as JSON
- `GET /photos/<filename>` - serves a captured image from `data/photos/`

The commands are suitable for scheduling with cron or another process supervisor.

## Database

`DatabaseManager` initializes three SQLite objects:

- `readings`: timestamped Celsius/Fahrenheit temperature, humidity, and VPD values.
- `photos`: captured image paths and timestamps.
- `daily_timelapse_summary`: a view that combines daily climate averages with the matching photo path.

The database path and photo path are relative to the project root when the normal module commands are used.

## Tests

Run the test suite from the project root:

```bash
pytest
```

The sensor tests cover VPD calculation and behavior when Raspberry Pi hardware libraries are unavailable. Database tests cover initialization and stored readings.

## Project layout

```text
plant-timelapse/
├── .env.example          # Template for environment configuration
├── .gitignore            # Ignores .env, __pycache__, and venv
├── README.md             # Project setup and usage documentation
├── requirements.txt      # Python dependencies
└── src/
    ├── app.py                 # Flask dashboard and API routes
    ├── main.py                # Sensor, photo, and AI CLI workflows
    ├── database/db.py         # SQLite tables, view, and queries
    ├── sensors/
    │   ├── camera.py          # Webcam capture
    │   └── dht11.py           # DHT11 reads and VPD calculation
    ├── services/
    │   ├── discord_bot.py     # Discord webhook reports
    │   └── genai.py           # Gemini image and climate analysis
    ├── templates/index.html   # Dashboard template
    └── tests/                 # Database and sensor tests
```