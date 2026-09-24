# src/tests/test_dht11.py

import unittest
from unittest.mock import patch
import math

from src.sensors.dht11 import DHT11Sensor
from src.services.discord_bot import _extract_json_payload
from src.services.genai import _extract_gemini_text


class TestDHT11Sensor(unittest.TestCase):

    # Simulate a machine without the Pi hardware libraries, even when running on the Pi
    @patch("src.sensors.dht11.adafruit_dht", None)
    @patch("src.sensors.dht11.board", None)
    def test_module_imports_without_hardware_dependencies(self):
        sensor = DHT11Sensor()
        self.assertIsNone(sensor.read())

    def test_calculate_vpd(self):
        temp_c = 25.0
        humidity = 50.0
        svp = 0.61078 * math.exp((17.27 * temp_c) / (temp_c + 237.3))
        avp = svp * (humidity / 100.0)
        expected_vpd = round(svp - avp, 2)

        self.assertEqual(DHT11Sensor.calculate_vpd(temp_c, humidity), expected_vpd)

    @patch.object(DHT11Sensor, 'read', return_value={'temperature_c': 25.0, 'humidity': 50.0})
    def test_read(self, mock_read):
        sensor = DHT11Sensor()
        self.assertEqual(sensor.read(), {'temperature_c': 25.0, 'humidity': 50.0})
        mock_read.assert_called_once()

    def test_exit(self):
        sensor = DHT11Sensor()
        sensor.exit()
        self.assertTrue(True)

    def test_extract_json_payload_from_markdown_fence(self):
        payload = '''```json
        {
          "visual_assessment": {"overall_health": "Good"},
          "climate_analysis": {"temperature": "Ideal"},
          "recommendations": ["Water more often"]
        }
        ```'''

        result = _extract_json_payload(payload)
        self.assertEqual(result["visual_assessment"]["overall_health"], "Good")
        self.assertEqual(result["recommendations"][0], "Water more often")

    def test_extract_gemini_text_from_candidates(self):
        class Part:
            text = '{"visual_assessment": {"overall_health": "Good"}}'

        class Candidate:
            def __init__(self):
                self.content = type('Content', (), {'parts': [Part()]})()

        class Response:
            text = None
            candidates = [Candidate()]

        result = _extract_gemini_text(Response())
        self.assertIn('"visual_assessment"', result)
        self.assertIn('"overall_health"', result)


if __name__ == '__main__':
    unittest.main()