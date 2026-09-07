"""Configuration for the ECG cleaner service."""

import os
from dotenv import load_dotenv

load_dotenv()

# The cleaner consumes raw dataset ECG rows and republishes canonical clean rows
# that the ingest service can write into structured InfluxDB columns.
MQTT_HOST = os.getenv("ECG_MQTT_HOST", "emqx")
MQTT_PORT = int(os.getenv("ECG_MQTT_PORT", "1883"))
MQTT_CLIENT_ID = os.getenv("ECG_CLEANER_MQTT_CLIENT_ID", "ecg-cleaner-service")
RAW_TOPIC = os.getenv("ECG_RAW_TOPIC", "tennis/ecg/raw")
CLEAN_TOPIC = os.getenv("ECG_CLEAN_TOPIC", "tennis/ecg/clean")
QOS = int(os.getenv("ECG_MQTT_QOS", "1"))
