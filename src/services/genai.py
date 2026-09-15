import json
import logging
import mimetypes
import os
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError


def _extract_gemini_text(response: Any) -> str | None:
    """Extract plain-text JSON from the SDK response object or nested candidates."""
    if response is None:
        return None

    text = getattr(response, "text", None)
    if text:
        return str(text)

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        if not content:
            continue
        parts = getattr(content, "parts", None) or []
        for part in parts:
            part_text = getattr(part, "text", None)
            if part_text:
                return str(part_text)
    return None


prompt = """
    You are an expert botanist and automated plant monitoring system. 

    Analyze the provided plant photo along with the real-time environmental metrics provided.

    ### YOUR TASK:
    1. Visual Assessment: Evaluate overall plant health, leaf posture, and signs of stress in the image.
    2. Climate Analysis: Assess if the VPD and temperature are within ideal ranges.
    3. Actionable Recommendations: Provide 2-3 concise recommendations.

    Return only a JSON object matching the provided response schema. Do not use
    Markdown, code fences, or additional commentary.
"""

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "visual_assessment": {
            "type": "object",
            "properties": {
                "overall_health": {"type": "string"},
                "leaf_posture": {"type": "string"},
                "signs_of_stress": {"type": "string"},
            },
            "required": ["overall_health", "leaf_posture", "signs_of_stress"],
        },
        "climate_analysis": {
            "type": "object",
            "properties": {
                "temperature": {"type": "string"},
                "vpd": {"type": "string"},
            },
            "required": ["temperature", "vpd"],
        },
        "recommendations": {
            "type": "array",
            "items": {"type": "string"},
        },
    },
    "required": ["visual_assessment", "climate_analysis", "recommendations"],
}


def send_gemini_report(
    daily_summary: dict[str, Any], GEMINI_API_KEY: str | None = None
) -> types.GenerateContentResponse | None:
    """Sends the aggregated reading data and photo to the Google Gemini API."""

    api_key = GEMINI_API_KEY or os.getenv("GEMINI_API_KEY")
    if not api_key:
        logging.error(
            "Gemini API key was not provided and GEMINI_API_KEY environment variable is not set."
        )
        return None

    # Locate the latest image in the photos directory safely
    photos_dir = Path("data/photos")
    if not photos_dir.exists() or not photos_dir.is_dir():
        logging.error(f"Photos directory does not exist: {photos_dir.resolve()}")
        return None

    image_files = list(photos_dir.glob("*.jpg")) + list(photos_dir.glob("*.png"))
    if not image_files:
        logging.error("No image files (.jpg, .png) found in the photos directory.")
        return None

    latest_image: Path | None = None
    try:
        latest_image = max(image_files, key=lambda p: p.stat().st_mtime)
        with latest_image.open("rb") as f:
            image_bytes = f.read()
    except (OSError, PermissionError) as e:
        logging.error(f"Failed to read image file '{latest_image or '<unknown>'}': {e}")
        return None

    mime_type, _ = mimetypes.guess_type(str(latest_image))
    if not mime_type:
        mime_type = "image/jpeg"

    # Safely convert daily summary dict/data to JSON text
    try:
        summary_text = json.dumps(daily_summary)
    except (TypeError, ValueError) as e:
        logging.error(f"Failed to serialize daily_summary to JSON: {e}")
        return None

    # Construct request parts
    try:
        text_part = types.Part.from_text(text=prompt)
        image_part = types.Part.from_bytes(data=image_bytes, mime_type=mime_type)
        data_part = types.Part.from_text(text=summary_text)
        content = types.Content(parts=[text_part, image_part, data_part])
    except Exception as e:
        logging.error(f"Failed to build Gemini Content payload: {e}")
        return None

    # Execute request to the Gemini API
    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=RESPONSE_SCHEMA,
            ),
            contents=[content],
        )

        extracted_text = _extract_gemini_text(response)
        if not extracted_text:
            logging.warning("Gemini API returned an empty or missing response payload.")
            return None

        logging.info("Successfully received report from Gemini API.")
        return response

    except APIError as e:
        logging.error(f"Google Gemini API error occurred: {e}")
    except Exception as e:
        logging.error(
            f"An unexpected error occurred while communicating with Gemini API: {e}",
            exc_info=True,
        )

    return None
