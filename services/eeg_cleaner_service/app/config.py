"""Configuration for the EEG cleaner service."""

import os
from dotenv import load_dotenv

load_dotenv()

# The cleaner consumes raw dataset EEG rows and republishes canonical clean rows
# that the ingest service can write into structured InfluxDB columns.
MQTT_HOST = os.getenv("EEG_MQTT_HOST", "emqx")
MQTT_PORT = int(os.getenv("EEG_MQTT_PORT", "1883"))
MQTT_CLIENT_ID = os.getenv("EEG_CLEANER_MQTT_CLIENT_ID", "eeg-cleaner-service")
RAW_TOPIC = os.getenv("EEG_RAW_TOPIC", "tennis/eeg/raw")
CLEAN_TOPIC = os.getenv("EEG_CLEAN_TOPIC", "tennis/eeg/clean")
QOS = int(os.getenv("EEG_MQTT_QOS", "1"))
CHANNEL_LIMIT = int(os.getenv("EEG_CHANNEL_LIMIT", "8"))
