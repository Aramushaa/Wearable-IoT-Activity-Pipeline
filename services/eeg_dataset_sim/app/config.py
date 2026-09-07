"""Configuration for the EEG OpenNeuro dataset replay service."""

import os
from dotenv import load_dotenv

load_dotenv()


def _int_env(name: str, default: int) -> int:
    """Read an integer environment variable with a typed default."""
    return int(os.getenv(name, str(default)))


def _float_env(name: str, default: float) -> float:
    """Read a float environment variable with a typed default."""
    return float(os.getenv(name, str(default)))


# Dataset controls define which BrainVision recording to replay and how much
# signal to emit during one container run.
DATASET_PATH = os.getenv("EEG_DATASET_PATH", "/app/dataset/openneuro_ds006848")
SUBJECT = os.getenv("EEG_SUBJECT", "sub-001")
TASK = os.getenv("EEG_TASK", "verbalwm")
MAX_SECONDS = _float_env("EEG_MAX_SECONDS", 30.0)
REPLAY_SPEED = _float_env("EEG_REPLAY_SPEED", 1.0)
STARTUP_DELAY_SECONDS = _float_env("EEG_STARTUP_DELAY_SECONDS", 5.0)
CHANNEL_LIMIT = _int_env("EEG_CHANNEL_LIMIT", 8)
DOWNSAMPLE_HZ = _float_env("EEG_DOWNSAMPLE_HZ", 100.0)

# MQTT settings mirror the cleaner service so raw EEG rows can flow through the
# same broker used by the rest of the pipeline.
MQTT_HOST = os.getenv("EEG_MQTT_HOST", "emqx")
MQTT_PORT = _int_env("EEG_MQTT_PORT", 1883)
RAW_TOPIC = os.getenv("EEG_RAW_TOPIC", "tennis/eeg/raw")
MQTT_QOS = _int_env("EEG_MQTT_QOS", 1)
