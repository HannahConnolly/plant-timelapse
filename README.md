# Plant Timelapse & Environmental Monitor

A Raspberry Pi plant-monitoring system. It reads a DHT11 temperature/humidity sensor every hour, takes a daily webcam photo, stores everything in SQLite, and serves a local web dashboard. Reports go to Discord: hourly sensor readings, a daily photo with climate averages, a daily Google Gemini plant-health assessment, and a weekly growth GIF.

## Features

- **Sensor readings**: DHT11 temperature and humidity on GPIO 4, with retries for the sensor's frequent timing errors.
- **VPD**: Vapor Pressure Deficit in kPa, calculated from the Tetens equation.
- **Daily photo**: A webcam capture saved as `data/photos/MM-DD-YYYY.jpg`.
- **History**: SQLite tables for readings and photos, plus a view of daily averages.
- **Dashboard**: A Flask page showing the latest photo and reading, and a JSON history API. It runs as a systemd service that starts on boot.
- **Discord reports**: Each report type can post to its own webhook.
  - Hourly: temperature, humidity and VPD.
  - Daily: the photo plus the day's average climate.
  - Daily: a Gemini 2.5 Flash assessment covering visual health, climate analysis and recommendations.
  - Weekly: a looping growth GIF built from every daily photo, with each frame labelled by date.
- **S3 backup** (optional): Each daily photo and weekly GIF is copied to an AWS S3 bucket.
- **Tests**: The suite runs on machines without the Raspberry Pi hardware libraries.

## Hardware

- Raspberry Pi running Raspberry Pi OS
- DHT11 temperature and humidity sensor
- USB webcam (opened as video device 0)
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

Then fill in `.env`. Never commit it; it is already in `.gitignore`.

| Variable | Used by | Notes |
| --- | --- | --- |
| `DISCORD_SENSOR_WEBHOOK_URL` | Hourly reading | Required for the default command |
| `DISCORD_PHOTO_WEBHOOK_URL` | Daily photo | Required for `--photo` |
| `DISCORD_GEMINI_WEBHOOK_URL` | Gemini assessment | Required for `--ai` |
| `GEMINI_API_KEY` | Gemini assessment | Required for `--ai` |
| `DISCORD_ANIMATION_WEBHOOK_URL` | Growth GIF | Optional; falls back to `DISCORD_PHOTO_WEBHOOK_URL` |

The `data/` directory, the SQLite database (`data/plant_monitor.db`), and the photo and animation folders are created automatically as needed. `data/` is git-ignored.

## Commands

`src/main.py` is the command-line entry point. Run it from the project root, because the camera and Gemini code use paths relative to it.

| Command | What it does |
| --- | --- |
| `python -m src.main` | Reads the DHT11, stores the reading, and posts it to the sensor webhook |
| `python -m src.main --photo` | Captures a webcam photo and posts it with today's climate averages |
| `python -m src.main --ai` | Sends the latest photo and today's averages to Gemini and posts the structured assessment |
| `python -m src.main --animation` | Builds a GIF from every daily photo (at least 2 are needed), saves it to `data/animations/`, and posts it |

The hardware modules can also be run on their own for a quick check:

```bash
python src/sensors/dht11.py    # prints a single reading as a table
python src/sensors/camera.py   # captures and saves one photo
```

## Scheduling with cron

The reports are run by the user's crontab (`crontab -e`). The current schedule:

```cron
# Hourly sensor reading
00 * * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py >> /home/hannah/plant-timelapse.log 2>&1
# Daily photo at 22:05
05 22 * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --photo >> /home/hannah/plant-timelapse.log 2>&1
# Daily Gemini assessment at 22:10, after the photo
10 22 * * * cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --ai >> /home/hannah/plant-timelapse.log 2>&1
# Weekly growth GIF, Saturdays at 22:15
15 22 * * 6 cd /home/hannah/plant-timelapse && /home/hannah/plant-timelapse/venv/bin/python src/main.py --animation >> /home/hannah/plant-timelapse.log 2>&1
```

All output is appended to `~/plant-timelapse.log`.

## Dashboard

The Flask dashboard runs on port 5000. Open `http://<raspberry-pi-ip>:5000/` to see the latest photo, temperature (°F), humidity and VPD.

| Route | Returns |
| --- | --- |
| `GET /` | Dashboard page |
| `GET /api/history` | The latest 24 readings as JSON |
| `GET /photos/<filename>` | A captured image from `data/photos/` |

To run it by hand for development:

```bash
python -m src.app
```

### Start the dashboard on boot

A systemd unit is included at `deploy/plant-dashboard.service`. It runs the dashboard as `hannah` from the project root, starts once the network is up, and restarts it 5 seconds after a crash. To install it:

```bash
sudo cp deploy/plant-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now plant-dashboard.service
```

Useful commands:

```bash
systemctl status plant-dashboard        # is it running?
journalctl -u plant-dashboard -f        # follow its logs
sudo systemctl restart plant-dashboard  # pick up code changes
```

After you edit the unit file, copy it again, run `daemon-reload`, and restart the service.

## Database

`DatabaseManager` (`src/database/db.py`) creates three SQLite objects:

- `readings`: timestamp, temperature in °C and °F, humidity, and VPD in kPa.
- `photos`: timestamp and file path of each captured image.
- `daily_timelapse_summary`: a view with each day's average temperature, humidity and VPD, joined to that day's photo path.

Timestamps use SQLite's `CURRENT_TIMESTAMP`, which is UTC. The daily view groups readings by UTC date.

## Gemini assessment

`--ai` sends Gemini 2.5 Flash three things: a botanist-style prompt, the most recently modified image in `data/photos/`, and the latest row of `daily_timelapse_summary`. The response is requested as JSON that matches this schema:

- `visual_assessment`: `overall_health`, `leaf_posture`, `signs_of_stress`
- `climate_analysis`: `temperature`, `vpd`
- `recommendations`: a list of 2 or 3 short actions

The result is posted to Discord as an embed titled "Automated Plant Health Assessment".

## AWS S3 backup

When `AWS_S3_BUCKET` is set in `.env`, `--photo` uploads each capture to `s3://<bucket>/photos/` and `--animation` uploads each GIF to `s3://<bucket>/animations/`. If an upload fails, the error is logged and the Discord report still goes out. If the variable is not set, nothing is uploaded.

### One-time setup

1. **Create an AWS account** at <https://aws.amazon.com>. Then, signed in as the root user:
   - Turn on MFA for the root user (account menu → **Security credentials**).
   - Create a budget alert (**Billing and Cost Management → Budgets → Create budget → Zero spend budget** or a monthly budget of about $5).

   After this, use the root user only for account settings.

2. **Create the bucket.** In the S3 console, choose **Create bucket**:
   - Name: must be unique across all of AWS, e.g. `plant-timelapse-<yourname>`.
   - Region: one near you, e.g. `eu-west-1`.
   - Leave **Block all public access** turned on.

3. **Create an IAM user for the Pi.** In the IAM console, go to **Users → Create user**, name it `plant-pi`, and leave console access off. Skip the permissions step. Open the new user, then **Add permissions → Create inline policy → JSON**, and paste this with your bucket name:

   ```json
   {
     "Version": "2012-10-17",
     "Statement": [
       {
         "Effect": "Allow",
         "Action": "s3:PutObject",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME/*"
       },
       {
         "Effect": "Allow",
         "Action": "s3:ListBucket",
         "Resource": "arn:aws:s3:::YOUR-BUCKET-NAME"
       }
     ]
   }
   ```

   This is least privilege: the Pi can add files to this one bucket and list them. It cannot read, delete or touch anything else in your account. Name the policy `plant-pi-s3-upload`.

4. **Create an access key.** On the user's **Security credentials** tab, choose **Create access key → Application running outside AWS**. Copy both values; the secret is shown only once.

5. **Configure the Pi.** Install the AWS CLI and store the key:

   ```bash
   sudo apt install awscli
   aws configure
   # AWS Access Key ID:     <from step 4>
   # AWS Secret Access Key: <from step 4>
   # Default region name:   <your bucket's region>
   # Default output format: json
   ```

   This writes `~/.aws/credentials` and `~/.aws/config`. boto3 reads these automatically, so the keys never go in `.env` or in the repo.

6. **Point the app at the bucket.** Add this to `.env`:

   ```dotenv
   AWS_S3_BUCKET="plant-timelapse-yourname"
   ```

### Check it works

```bash
aws sts get-caller-identity              # shows the plant-pi user, so the credentials work
python -m src.main --photo               # log should end with "Backed up ... to s3://..."
aws s3 ls s3://plant-timelapse-yourname/photos/
```

`aws s3 rm` fails with `AccessDenied`, which is expected, because the policy doesn't allow deletes.

To copy photos taken before S3 was set up:

```bash
aws s3 sync data/photos/ s3://plant-timelapse-yourname/photos/
```

## Tests

From the project root:

```bash
pytest
```

The tests cover:

- **Database**: initialization, inserting and reading back readings, and photo path normalization for the file server.
- **Sensor**: VPD maths, reads and cleanup, and importing without the hardware libraries.
- **Parsing**: extracting JSON from Gemini and Discord responses.
- **Animation**: photo collection and ordering, GIF output, and skipping unreadable images.
- **S3 backup**: object key and content type, and failed uploads returning `None` (the S3 client is mocked, so no AWS account is needed).

## Project layout

```text
plant-timelapse/
├── .env.example                  # Template for environment configuration
├── README.md
├── requirements.txt              # Python dependencies
├── deploy/
│   └── plant-dashboard.service   # systemd unit that starts the dashboard on boot
├── data/                         # Created at runtime (git-ignored)
│   ├── plant_monitor.db          # SQLite database
│   ├── photos/                   # Daily captures, MM-DD-YYYY.jpg
│   └── animations/               # Generated growth GIFs
└── src/
    ├── app.py                    # Flask dashboard and API routes
    ├── main.py                   # CLI: sensor, photo, AI, and animation workflows
    ├── database/db.py            # SQLite tables, view, and queries
    ├── sensors/
    │   ├── camera.py             # Webcam capture
    │   └── dht11.py              # DHT11 reads and VPD calculation
    ├── services/
    │   ├── animation.py          # Growth GIF builder
    │   ├── discord_bot.py        # Discord webhook reports
    │   ├── genai.py              # Gemini image and climate analysis
    │   └── s3_backup.py          # Optional S3 upload of photos and GIFs
    ├── static/favicon.ico
    ├── templates/index.html      # Dashboard template
    └── tests/                    # Database, sensor, and animation tests
```
