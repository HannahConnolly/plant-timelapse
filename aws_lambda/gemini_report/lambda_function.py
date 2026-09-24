"""AWS Lambda: when a daily photo lands in S3, ask Gemini for a plant health report and post it to Discord.

Triggered by S3 ObjectCreated events on photos/*.jpg. It uses only the standard library and boto3
(built into the Lambda Python runtime), so this one file is the whole deployment.

The prompt and response schema mirror src/services/genai.py; keep them in sync.
"""

import base64
import json
import logging
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta
from pathlib import PurePosixPath
from urllib.parse import unquote_plus

import boto3
from boto3.dynamodb.conditions import Key

logger = logging.getLogger()
logger.setLevel(logging.INFO)

TABLE_NAME = os.environ.get("TABLE_NAME", "plant-readings")
DEVICE_ID = os.environ.get("DEVICE_ID", "plant-pi")
PARAMETER_PREFIX = os.environ.get("PARAMETER_PREFIX", "/plant-timelapse")
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Seconds to wait between attempts when Gemini is overloaded; keep the Lambda timeout above their sum
GEMINI_RETRY_DELAYS = [5, 15]
RETRYABLE_STATUS_CODES = {429, 500, 503}
# Discord's Cloudflare front end rejects Python's default urllib user agent
USER_AGENT = "plant-timelapse-lambda (https://github.com/HannahConnolly/plant-timelapse, 1.0)"

# Matches the filename format written by src/sensors/camera.py
PHOTO_DATE_FORMAT = "%m-%d-%Y"
# Older photos are skipped so a bulk `aws s3 sync` doesn't trigger a report per photo
MAX_PHOTO_AGE_DAYS = 1

PROMPT = """
    You are an expert botanist and automated plant monitoring system.

    Analyze the provided plant photo along with the environmental metrics provided,
    which are averages over the last 24 hours.

    ### YOUR TASK:
    1. Visual Assessment: Evaluate overall plant health, leaf posture, and signs of stress in the image.
    2. Climate Analysis: Assess if the VPD and temperature are within ideal ranges.
    3. Actionable Recommendations: Provide 2-3 concise recommendations.

    Return only a JSON object matching the provided response schema. Do not use
    Markdown, code fences, or additional commentary.
"""

# The REST API expects upper-case OpenAPI type names (the Python SDK converts them for you)
RESPONSE_SCHEMA = {
    "type": "OBJECT",
    "properties": {
        "visual_assessment": {
            "type": "OBJECT",
            "properties": {
                "overall_health": {"type": "STRING"},
                "leaf_posture": {"type": "STRING"},
                "signs_of_stress": {"type": "STRING"},
            },
            "required": ["overall_health", "leaf_posture", "signs_of_stress"],
        },
        "climate_analysis": {
            "type": "OBJECT",
            "properties": {
                "temperature": {"type": "STRING"},
                "vpd": {"type": "STRING"},
            },
            "required": ["temperature", "vpd"],
        },
        "recommendations": {"type": "ARRAY", "items": {"type": "STRING"}},
    },
    "required": ["visual_assessment", "climate_analysis", "recommendations"],
}

# Created on first use and reused while the Lambda container stays warm
_clients = {}
_parameters = {}


def _client(name: str):
    if name not in _clients:
        _clients[name] = boto3.resource(name) if name == "dynamodb" else boto3.client(name)
    return _clients[name]


def get_parameter(name: str) -> str:
    """Reads a SecureString from SSM Parameter Store, cached for the life of the container."""
    if name not in _parameters:
        response = _client("ssm").get_parameter(
            Name=f"{PARAMETER_PREFIX}/{name}", WithDecryption=True
        )
        _parameters[name] = response["Parameter"]["Value"]
    return _parameters[name]


def photo_date_from_key(key: str) -> date | None:
    try:
        return datetime.strptime(PurePosixPath(key).stem, PHOTO_DATE_FORMAT).date()
    except ValueError:
        return None


def should_process(key: str, event_time: datetime) -> bool:
    """Only reports on fresh daily photos, not test files or backfilled old photos."""
    photo_date = photo_date_from_key(key)
    if photo_date is None:
        logger.info(f"Skipping {key}: not a dated daily photo")
        return False

    # event_time is UTC, so a 22:05 local photo can already be "tomorrow"; allow one day
    age_days = (event_time.date() - photo_date).days
    if age_days > MAX_PHOTO_AGE_DAYS:
        logger.info(f"Skipping {key}: photo is {age_days} days old (likely a backfill upload)")
        return False
    return True


def fetch_recent_readings(now: datetime, hours: int = 24) -> list[dict]:
    """Queries DynamoDB for this device's readings since `hours` ago, using the sort key."""
    since = (now - timedelta(hours=hours)).strftime("%Y-%m-%dT%H:%M:%SZ")
    table = _client("dynamodb").Table(TABLE_NAME)
    response = table.query(
        KeyConditionExpression=Key("device_id").eq(DEVICE_ID) & Key("timestamp").gte(since)
    )
    return response["Items"]


def summarize_readings(items: list[dict]) -> dict:
    """Averages each metric, skipping readings where the sensor returned nothing."""
    summary = {"period": "last 24 hours", "reading_count": len(items)}
    for field in ("temperature_c", "temperature_f", "humidity", "vpd_kpa"):
        # DynamoDB returns numbers as Decimal
        values = [float(item[field]) for item in items if item.get(field) is not None]
        summary[f"avg_{field}"] = round(sum(values) / len(values), 2) if values else None
    return summary


def build_gemini_request(image_bytes: bytes, summary: dict) -> dict:
    return {
        "contents": [
            {
                "parts": [
                    {"text": PROMPT},
                    {
                        "inline_data": {
                            "mime_type": "image/jpeg",
                            "data": base64.b64encode(image_bytes).decode("ascii"),
                        }
                    },
                    {"text": json.dumps(summary)},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": RESPONSE_SCHEMA,
        },
    }


def parse_gemini_response(body: dict) -> dict:
    text = body["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(text)


def call_gemini(api_key: str, image_bytes: bytes, summary: dict) -> dict:
    request = urllib.request.Request(
        GEMINI_URL.format(model=GEMINI_MODEL),
        data=json.dumps(build_gemini_request(image_bytes, summary)).encode(),
        headers={"Content-Type": "application/json", "x-goog-api-key": api_key},
    )
    for attempt, delay in enumerate(GEMINI_RETRY_DELAYS + [None], start=1):
        try:
            with urllib.request.urlopen(request, timeout=45) as response:
                return parse_gemini_response(json.load(response))
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace")[:500]
            # 429/5xx mean Gemini is busy; wait and retry before giving up
            if e.code in RETRYABLE_STATUS_CODES and delay is not None:
                logger.warning(f"Gemini returned {e.code} (attempt {attempt}); retrying in {delay}s")
                time.sleep(delay)
                continue
            raise RuntimeError(f"Gemini API returned {e.code}: {detail}") from e


def build_discord_embed(report: dict, summary: dict, filename: str) -> dict:
    visual = report.get("visual_assessment", {})
    climate = report.get("climate_analysis", {})
    recommendations = report.get("recommendations", [])
    if isinstance(recommendations, list) and recommendations:
        rec_text = "\n".join(f"• {rec}" for rec in recommendations)
    else:
        rec_text = "No immediate adjustments required."

    return {
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
        "image": {"url": f"attachment://{filename}"},
        "footer": {
            "text": f"Gemini via AWS Lambda • {summary['reading_count']} readings from the last 24h"
        },
    }


def build_multipart(payload: dict, image_bytes: bytes, filename: str) -> tuple[bytes, str]:
    """Encodes the embed and photo as multipart/form-data, the way Discord expects attachments."""
    boundary = uuid.uuid4().hex
    body = b"".join(
        [
            f"--{boundary}\r\n".encode(),
            b'Content-Disposition: form-data; name="payload_json"\r\n',
            b"Content-Type: application/json\r\n\r\n",
            json.dumps(payload).encode(),
            b"\r\n",
            f"--{boundary}\r\n".encode(),
            f'Content-Disposition: form-data; name="files[0]"; filename="{filename}"\r\n'.encode(),
            b"Content-Type: image/jpeg\r\n\r\n",
            image_bytes,
            b"\r\n",
            f"--{boundary}--\r\n".encode(),
        ]
    )
    return body, f"multipart/form-data; boundary={boundary}"


def post_to_discord(webhook_url: str, embed: dict, image_bytes: bytes, filename: str) -> None:
    body, content_type = build_multipart({"embeds": [embed]}, image_bytes, filename)
    request = urllib.request.Request(
        webhook_url, data=body, headers={"Content-Type": content_type, "User-Agent": USER_AGENT}
    )
    try:
        with urllib.request.urlopen(request, timeout=15):
            pass
    except urllib.error.HTTPError as e:
        detail = e.read().decode(errors="replace")[:500]
        raise RuntimeError(f"Discord returned {e.code}: {detail}") from e


def process_photo(bucket: str, key: str, event_time: datetime) -> str:
    if not should_process(key, event_time):
        return "skipped"

    image_bytes = _client("s3").get_object(Bucket=bucket, Key=key)["Body"].read()
    summary = summarize_readings(fetch_recent_readings(event_time))
    logger.info(f"Climate summary: {json.dumps(summary)}")

    report = call_gemini(get_parameter("gemini-api-key"), image_bytes, summary)
    logger.info(f"Gemini report: {json.dumps(report)}")

    filename = PurePosixPath(key).name
    embed = build_discord_embed(report, summary, filename)
    post_to_discord(get_parameter("discord-gemini-webhook"), embed, image_bytes, filename)
    logger.info(f"Posted report for {key} to Discord")
    return "posted"


def lambda_handler(event, context):
    """Entry point. An S3 event can carry several records, so each photo is handled in turn."""
    results = {}
    for record in event.get("Records", []):
        bucket = record["s3"]["bucket"]["name"]
        # S3 URL-encodes keys in events (spaces arrive as '+')
        key = unquote_plus(record["s3"]["object"]["key"])
        event_time = datetime.fromisoformat(record["eventTime"].replace("Z", "+00:00"))
        results[key] = process_photo(bucket, key, event_time)
    return results
