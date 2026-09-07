"""Environment-driven configuration for the ingest service.

Values are loaded once at process start. Keep validation here so the rest of
the service can safely build SQL and MQTT subscriptions from these constants.
"""

import os
from dotenv import load_dotenv

from .utils.validators import validate_table_name

load_dotenv()

# MQTT broker and topics used by the background subscriber.
MQTT_HOST = os.getenv("MQTT_HOST", "localhost")
MQTT_PORT = int(os.getenv("MQTT_PORT", "1883"))

# Multiple MQTT subscriptions are configured as a comma-separated string so the
# Docker `.env` file can opt into new streams without code changes.
SUB_TOPICS = os.getenv(
    "SUB_TOPICS",
    "tennis/sensor/+/events,tennis/camera/+/ball"
)
SUB_TOPICS = [t.strip() for t in SUB_TOPICS.split(",") if t.strip()]

# Optional debug publishing topic used by the `/publish` endpoint.
PUB_TOPIC = os.getenv("PUB_TOPIC", "tennis/sensor/1/events")

EVENT_BUFFER_MAX = int(os.getenv("EVENT_BUFFER_MAX", "100"))

# Generic events keep the original MQTT payload as JSON for debugging; the
# structured writers below store queryable sensor columns.
INFLUX_WRITE_GENERIC_EVENTS = os.getenv("INFLUX_WRITE_GENERIC_EVENTS", "1") == "1"

INFLUX_ENABLED = os.getenv("INFLUX_ENABLED", "0") == "1"
INFLUX_HOST = os.getenv("INFLUX_HOST", "http://localhost:8181")
INFLUX_TOKEN = os.getenv("INFLUX_TOKEN", "")
INFLUX_DATABASE = os.getenv("INFLUX_DATABASE", "tennis")

INFLUX_TABLE = validate_table_name(
    os.getenv("INFLUX_TABLE", "events"),
    "INFLUX_TABLE",
)
INFLUX_IMU_TABLE = validate_table_name(
    os.getenv("INFLUX_IMU_TABLE", "imu_raw"),
    "INFLUX_IMU_TABLE",
)

# Real watch data is routed to a separate table so dataset validation and real
# hardware experiments do not mix.
INFLUX_WATCH_IMU_TABLE = validate_table_name(
    os.getenv("INFLUX_WATCH_IMU_TABLE", "watch_imu_clean"),
    "INFLUX_WATCH_IMU_TABLE",
)

INFLUX_EEG_TABLE = validate_table_name(
    os.getenv("INFLUX_EEG_TABLE", "eeg_clean"),
    "INFLUX_EEG_TABLE",
)
INFLUX_ECG_TABLE = validate_table_name(
    os.getenv("INFLUX_ECG_TABLE", "ecg_clean"),
    "INFLUX_ECG_TABLE",
)

# The ingest service writes through an in-memory queue so MQTT callbacks do not
# block on HTTP writes to InfluxDB.
INFLUX_BATCH_SIZE = int(os.getenv("INFLUX_BATCH_SIZE", "500"))
INFLUX_FLUSH_INTERVAL_MS = int(os.getenv("INFLUX_FLUSH_INTERVAL_MS", "200"))
INFLUX_MAX_QUEUE_SIZE = int(os.getenv("INFLUX_MAX_QUEUE_SIZE", "50000"))
