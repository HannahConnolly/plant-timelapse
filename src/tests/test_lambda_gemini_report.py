import importlib.util
import io
import json
import unittest
import urllib.error
from datetime import datetime, timezone
from decimal import Decimal
from email.parser import BytesParser
from email.policy import HTTP
from pathlib import Path
from unittest.mock import MagicMock, patch

# The Lambda lives outside src/ because it's deployed on its own, so load it by path
LAMBDA_PATH = Path(__file__).resolve().parents[2] / "aws_lambda" / "gemini_report" / "lambda_function.py"
spec = importlib.util.spec_from_file_location("lambda_function", LAMBDA_PATH)
lf = importlib.util.module_from_spec(spec)
spec.loader.exec_module(lf)

EVENT_TIME = datetime(2026, 9, 25, 2, 5, 3, tzinfo=timezone.utc)  # 22:05 EDT on 09-24
REPORT = {
    "visual_assessment": {"overall_health": "Good", "leaf_posture": "Upright", "signs_of_stress": "None"},
    "climate_analysis": {"temperature": "Ideal", "vpd": "Ideal"},
    "recommendations": ["Keep going"],
}


class TestShouldProcess(unittest.TestCase):
    def test_todays_photo_is_processed_even_after_utc_midnight(self):
        self.assertTrue(lf.should_process("photos/09-24-2026.jpg", EVENT_TIME))

    def test_old_backfilled_photo_is_skipped(self):
        self.assertFalse(lf.should_process("photos/09-13-2026.jpg", EVENT_TIME))

    def test_undated_file_is_skipped(self):
        self.assertFalse(lf.should_process("photos/demo.jpg", EVENT_TIME))


class TestSummarizeReadings(unittest.TestCase):
    def test_averages_decimals_and_skips_missing_values(self):
        items = [
            {"temperature_c": Decimal("25"), "temperature_f": Decimal("77"), "humidity": Decimal("70"), "vpd_kpa": Decimal("0.9")},
            {"temperature_c": Decimal("27"), "temperature_f": Decimal("80.6"), "humidity": None, "vpd_kpa": Decimal("1.1")},
        ]

        summary = lf.summarize_readings(items)

        self.assertEqual(summary["reading_count"], 2)
        self.assertEqual(summary["avg_temperature_c"], 26.0)
        self.assertEqual(summary["avg_humidity"], 70.0)
        self.assertEqual(summary["avg_vpd_kpa"], 1.0)

    def test_no_readings_gives_none_averages(self):
        summary = lf.summarize_readings([])

        self.assertEqual(summary["reading_count"], 0)
        self.assertIsNone(summary["avg_temperature_f"])


class TestGemini(unittest.TestCase):
    def test_request_includes_prompt_image_and_schema(self):
        request = lf.build_gemini_request(b"jpeg-bytes", {"reading_count": 3})

        parts = request["contents"][0]["parts"]
        self.assertEqual(parts[1]["inline_data"], {"mime_type": "image/jpeg", "data": "anBlZy1ieXRlcw=="})
        self.assertEqual(json.loads(parts[2]["text"]), {"reading_count": 3})
        self.assertEqual(request["generationConfig"]["responseSchema"]["type"], "OBJECT")

    def test_parse_response_reads_json_text(self):
        body = {"candidates": [{"content": {"parts": [{"text": json.dumps(REPORT)}]}}]}

        self.assertEqual(lf.parse_gemini_response(body), REPORT)

    @patch.object(lf.time, "sleep")
    @patch.object(lf.urllib.request, "urlopen")
    def test_retries_when_gemini_is_busy(self, urlopen, sleep):
        busy = urllib.error.HTTPError("url", 503, "Service Unavailable", {}, io.BytesIO(b"busy"))
        ok = MagicMock()
        ok.__enter__.return_value = io.BytesIO(
            json.dumps({"candidates": [{"content": {"parts": [{"text": json.dumps(REPORT)}]}}]}).encode()
        )
        urlopen.side_effect = [busy, ok]

        self.assertEqual(lf.call_gemini("key", b"img", {}), REPORT)
        sleep.assert_called_once_with(lf.GEMINI_RETRY_DELAYS[0])

    @patch.object(lf.urllib.request, "urlopen")
    def test_bad_request_is_not_retried(self, urlopen):
        urlopen.side_effect = urllib.error.HTTPError("url", 400, "Bad Request", {}, io.BytesIO(b"bad"))

        with self.assertRaises(RuntimeError):
            lf.call_gemini("key", b"img", {})
        urlopen.assert_called_once()


class TestDiscord(unittest.TestCase):
    def test_multipart_carries_embed_and_photo(self):
        embed = lf.build_discord_embed(REPORT, {"reading_count": 20}, "09-24-2026.jpg")
        body, content_type = lf.build_multipart({"embeds": [embed]}, b"jpeg-bytes", "09-24-2026.jpg")

        message = BytesParser(policy=HTTP).parsebytes(
            f"Content-Type: {content_type}\r\n\r\n".encode() + body
        )
        payload_part, file_part = message.iter_parts()
        payload = json.loads(payload_part.get_content())
        self.assertEqual(payload["embeds"][0]["image"]["url"], "attachment://09-24-2026.jpg")
        self.assertIn("20 readings", payload["embeds"][0]["footer"]["text"])
        self.assertEqual(file_part.get_filename(), "09-24-2026.jpg")
        self.assertEqual(file_part.get_content(), b"jpeg-bytes")


class TestHandler(unittest.TestCase):
    def test_handler_decodes_key_and_passes_event_time(self):
        event = {
            "Records": [
                {
                    "eventTime": "2026-09-25T02:05:03.000Z",
                    "s3": {"bucket": {"name": "bucket"}, "object": {"key": "photos/09-24-2026.jpg"}},
                }
            ]
        }
        with patch.object(lf, "process_photo", return_value="posted") as process_photo:
            result = lf.lambda_handler(event, None)

        self.assertEqual(result, {"photos/09-24-2026.jpg": "posted"})
        process_photo.assert_called_once_with("bucket", "photos/09-24-2026.jpg", EVENT_TIME)

    def test_skipped_photo_touches_no_aws_services(self):
        with patch.object(lf, "_client") as client:
            self.assertEqual(lf.process_photo("bucket", "photos/demo.jpg", EVENT_TIME), "skipped")
        client.assert_not_called()


if __name__ == "__main__":
    unittest.main()
