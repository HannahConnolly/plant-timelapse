import json
import logging
from pathlib import Path
from typing import Any

from awscrt import mqtt
from awscrt.exceptions import AwsCrtError
from awsiot import mqtt_connection_builder

logger = logging.getLogger(__name__)

TIMEOUT_SECONDS = 10

# File names used when saving the certificates downloaded from the IoT console
CERT_FILE = "certificate.pem.crt"
KEY_FILE = "private.pem.key"
ROOT_CA_FILE = "AmazonRootCA1.pem"


def build_reading_payload(reading: dict[str, Any], device_id: str) -> dict[str, Any]:
    """Shapes a database reading into the JSON message stored in DynamoDB."""
    return {
        "device_id": device_id,
        # SQLite CURRENT_TIMESTAMP is UTC; ISO 8601 sorts correctly as a DynamoDB sort key
        "timestamp": reading["timestamp"].replace(" ", "T") + "Z",
        "temperature_c": reading.get("temperature_c"),
        "temperature_f": reading.get("temperature_f"),
        "humidity": reading.get("humidity"),
        "vpd_kpa": reading.get("vpd_kpa"),
    }


def publish_reading(
    reading: dict[str, Any], endpoint: str, cert_dir: Path, device_id: str, connection=None
) -> bool:
    """Publishes a reading to plant/<device_id>/readings over MQTT. Returns True on success."""
    topic = f"plant/{device_id}/readings"
    payload = json.dumps(build_reading_payload(reading, device_id))

    try:
        if connection is None:
            cert_dir = Path(cert_dir)
            # Mutual TLS: the device certificate proves to AWS that this is the plant-pi Thing
            connection = mqtt_connection_builder.mtls_from_path(
                endpoint=endpoint,
                cert_filepath=str(cert_dir / CERT_FILE),
                pri_key_filepath=str(cert_dir / KEY_FILE),
                ca_filepath=str(cert_dir / ROOT_CA_FILE),
                client_id=device_id,
                clean_session=True,
                keep_alive_secs=30,
            )
        connection.connect().result(TIMEOUT_SECONDS)
        publish_future, _ = connection.publish(
            topic=topic, payload=payload, qos=mqtt.QoS.AT_LEAST_ONCE
        )
        publish_future.result(TIMEOUT_SECONDS)
        connection.disconnect().result(TIMEOUT_SECONDS)
    except (AwsCrtError, TimeoutError, OSError) as e:
        # A failed publish shouldn't stop the Discord report, so log and carry on
        logger.error(f"AWS IoT publish to '{topic}' failed: {e}")
        return False

    logger.info(f"Published reading to AWS IoT topic '{topic}'")
    return True
