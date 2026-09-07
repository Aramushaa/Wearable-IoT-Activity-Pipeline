"""Configuration for the MetaWear watch cleaner service."""

import os
from dotenv import load_dotenv

load_dotenv()

# These settings use CLEANER_* first, then the generic MQTT_* values, so the
# cleaner can run either as part of Docker Compose or as a standalone process.
MQTT_HOST = os.getenv("CLEANER_MQTT_HOST", os.getenv("MQTT_HOST", "emqx"))
MQTT_PORT = int(os.getenv("CLEANER_MQTT_PORT", os.getenv("MQTT_PORT", "1883")))
MQTT_CLIENT_ID = os.getenv("CLEANER_MQTT_CLIENT_ID", "watch-cleaner-service")

RAW_TOPIC = os.getenv("CLEANER_RAW_TOPIC", "tennis/watch/raw")
CLEAN_TOPIC = os.getenv("CLEANER_CLEAN_TOPIC", "tennis/watch/clean")
QOS = int(os.getenv("CLEANER_MQTT_QOS", "1"))

# Conservative physical sanity bounds. These are not ML preprocessing;
# they are validation guards to avoid storing broken rows.
MAX_ABS_ACC = float(os.getenv("CLEANER_MAX_ABS_ACC", "80"))
MAX_ABS_GYRO = float(os.getenv("CLEANER_MAX_ABS_GYRO", "2500"))
MAX_PAIR_AGE_SECONDS = float(os.getenv("CLEANER_MAX_PAIR_AGE_SECONDS", "0.25"))
DEFAULT_ACTIVITY_GT = os.getenv("CLEANER_DEFAULT_ACTIVITY_GT", "unknown")
