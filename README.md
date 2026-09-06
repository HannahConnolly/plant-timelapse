# Plant Timelapse & Environmental Monitor

A Raspberry Pi utility that captures periodic photos from a connected webcam, reads ambient temperature and humidity data from a DHT11 sensor, and posts formatted status updates to a Discord channel.

---

## Hardware Requirements

* **Raspberry Pi** (Running Raspberry Pi OS)
* **DHT11 Temperature & Humidity Sensor** (3-pin breakout or 4-pin with a 10kΩ resistor)
* **USB Webcam**
* Jumper Wires & Breadboard

### GPIO Wiring (DHT11)
| DHT11 Pin | Raspberry Pi Pin |
| :--- | :--- |
| **VCC** | 3.3V (Pin 1) or 5V (Pin 2) |
| **DATA** | GPIO 4 (Pin 7) |
| **GND** | Ground (Pin 6) |

---

## Directory Structure

```text
plant-timelapse/
├── .env.example          # Template for environment configuration
├── .gitignore            # Ignores .env, __pycache__, and venv
├── README.md             # Project setup and usage documentation
├── requirements.txt      # Python dependencies
└── src/
    ├── __init__.py
    ├── main.py           # Application entry point
    ├── sensors/
    │   ├── __init__.py
    │   ├── dht11.py      # Sensor reading logic
    │   └── camera.py     # Image capture logic
    └── services/
        ├── __init__.py
        └── discord_bot.py # Discord webhook/bot dispatch logic