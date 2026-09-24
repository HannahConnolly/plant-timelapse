import json
import unittest
from unittest.mock import MagicMock

from awscrt import mqtt
from awscrt.exceptions import AwsCrtError

from src.services.iot_publisher import build_reading_payload, publish_reading

READING = {
    "id": 292,
    "timestamp": "2026-09-24 17:00:06",
    "temperature_c": 25.3,
    "temperature_f": 77.5,
    "humidity": 73.0,
    "vpd_kpa": 0.87,
    "file_path": "data/photos/09-23-2026.jpg",
}


class TestIoTPublisher(unittest.TestCase):
    def test_payload_has_keys_and_iso_timestamp(self):
        payload = build_reading_payload(READING, "plant-pi")

        self.assertEqual(
            payload,
            {
                "device_id": "plant-pi",
                "timestamp": "2026-09-24T17:00:06Z",
                "temperature_c": 25.3,
                "temperature_f": 77.5,
                "humidity": 73.0,
                "vpd_kpa": 0.87,
            },
        )

    def test_publish_sends_json_to_device_topic(self):
        connection = MagicMock()
        connection.publish.return_value = (MagicMock(), 1)

        self.assertTrue(publish_reading(READING, "endpoint", "certs", "plant-pi", connection))

        kwargs = connection.publish.call_args.kwargs
        self.assertEqual(kwargs["topic"], "plant/plant-pi/readings")
        self.assertEqual(kwargs["qos"], mqtt.QoS.AT_LEAST_ONCE)
        self.assertEqual(json.loads(kwargs["payload"])["humidity"], 73.0)
        connection.disconnect.assert_called_once()

    def test_publish_failure_returns_false(self):
        connection = MagicMock()
        connection.connect.return_value.result.side_effect = AwsCrtError(
            1, "AWS_IO_TLS_ERROR_NEGOTIATION_FAILURE", "TLS negotiation failed"
        )

        self.assertFalse(publish_reading(READING, "endpoint", "certs", "plant-pi", connection))


if __name__ == "__main__":
    unittest.main()
