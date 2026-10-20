# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

Run everything from the project root (camera and Gemini code use paths relative to it). Activate the venv first: `source venv/bin/activate`.

```bash
pytest                                                          # full suite; works without Pi hardware libs
pytest src/tests/test_db.py::TestDatabase::test_init_db         # single test
python -m src.main                       # hourly: read DHT11, store, publish to IoT, post to Discord
python -m src.main --photo               # webcam photo + daily climate averages to Discord (and S3)
python -m src.main --ai                  # Gemini assessment from the Pi (normally done by Lambda now)
python -m src.main --animation           # growth GIF from all photos (needs >= 2)
python -m src.app                        # Flask dashboard on :5000
```

There is no lint/build config. Production runs via the user's crontab (hourly/daily/weekly entries calling `src/main.py`) and the `deploy/plant-dashboard.service` systemd unit; see README for the schedule and AWS setup walkthroughs.

## Architecture

Raspberry Pi app plus an optional AWS pipeline. `src/main.py` is a thin CLI that dispatches on a single flag (`--photo`, `--animation`, `--ai`, or default sensor reading) and wires together modules in `src/sensors/` (DHT11, webcam), `src/services/` (Discord, Gemini, S3, IoT Core, GIF) and `src/database/db.py` (SQLite at `data/plant_monitor.db`, git-ignored).

Data flow across the system:
- Hourly: sensor → SQLite → (if `AWS_IOT_ENDPOINT`) MQTT to IoT Core → IoT Rule → DynamoDB `plant-readings`, plus a Discord post.
- Daily 22:05: photo → SQLite → (if `AWS_S3_BUCKET`) S3 `photos/` → triggers Lambda `aws_lambda/gemini_report/lambda_function.py`, which reads the last 24h from DynamoDB, secrets from SSM Parameter Store, calls Gemini and posts to Discord.
- Weekly: GIF built from `data/photos/MM-DD-YYYY.jpg` → S3 `animations/` + Discord.

Things that span multiple files:
- **Gemini logic is duplicated**: the prompt and response schema in `src/services/genai.py` are mirrored in the Lambda (a single stdlib+boto3 file, no packaging). Keep them in sync. The two also aggregate differently: `--ai` uses the UTC calendar day (`daily_timelapse_summary` view), Lambda uses a rolling 24h.
- **The Lambda is deployed by hand**: edits to `lambda_function.py` only take effect after pasting the file into the Lambda console and clicking Deploy.
- **AWS and Discord failures are non-fatal**: S3/IoT errors are logged and the Discord report still goes out; the optional integrations are skipped entirely when their env var is unset.
- **Timestamps are UTC** (SQLite `CURRENT_TIMESTAMP`), so the daily view groups by UTC date.
- **Dual imports**: `main.py` tries `src.*` imports then falls back to bare imports so it works both as `python -m src.main` and `python src/main.py` (cron). Preserve that when adding modules.
- **VPD thresholds** (ideal 0.8–1.5 kPa, red outside 0.4–1.8) live in `src/services/discord_bot.py` and drive embed colors.
- **Failed sensor reads still create a row**: `process_sensor_reading` does `sensor.read() or {}`, so a failed DHT11 read inserts a row of NULLs, publishes it to IoT Core (null fields reach DynamoDB) and posts "N/A" values to Discord. SQLite `AVG()` ignores NULLs, but check the Lambda's averaging before relying on it.
- **Don't run hardware commands off the Pi**: the default command and `--photo` need the DHT11/webcam, and `--photo` writes to `data/photos/` and posts to Discord. Use `pytest` to verify changes elsewhere.
- **Photo filenames carry the date** (`MM-DD-YYYY.jpg`): the animation builder orders frames by it, and the Lambda skips photos with no date or older than a day. Renaming or backfilling photos can silently break both.
- Hardware libs (DHT11/camera) must stay importable without the hardware so tests run on any machine; AWS/HTTP calls are mocked in tests.

Config is via `.env` (see `.env.example`); IoT device certs live outside the repo in `~/.plant-iot`, and AWS credentials come from `~/.aws`, never `.env`.
