"""MQTT cleaner that validates raw EEG rows and publishes canonical rows."""

from __future__ import annotations

import json
import logging
import math
import time
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from .config import CHANNEL_LIMIT, CLEAN_TOPIC, MQTT_CLIENT_ID, MQTT_HOST, MQTT_PORT, QOS, RAW_TOPIC

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)


def now_iso() -> str:
    """Return a compact UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _float_value(payload: dict[str, Any], key: str) -> float:
    """Read a required finite float from a raw EEG payload."""
    value = float(payload[key])
    if not math.isfinite(value):
        raise ValueError(f"{key} must be finite")
    return value


def clean_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Validate raw EEG JSON and return the canonical clean payload."""
    channels_obj = payload.get("channels")
    if not isinstance(channels_obj, dict) or not channels_obj:
        raise ValueError("channels must be a non-empty object")

    channels: dict[str, float] = {}
    for name, value in channels_obj.items():
        # Limit channel count at the cleaner boundary so downstream storage and
        # dashboards have a predictable schema size.
        if len(channels) >= CHANNEL_LIMIT:
            break
        channel_value = float(value)
        if not math.isfinite(channel_value):
            raise ValueError(f"channel {name} must be finite")
        channels[str(name)] = channel_value

    if not channels:
        raise ValueError("no valid EEG channels")

    sensor_ts = _float_value(payload, "sensor_ts")

    return {
        "source": str(payload.get("source", "openneuro_ds006848")),
        "device": "eeg",
        "subject": str(payload.get("subject", "sub-001")),
        "task": str(payload.get("task", "verbalwm")),
        "recording_id": str(payload.get("recording_id", "unknown")),
        "sensor_ts": sensor_ts,
        "dataset_ts": sensor_ts,
        "sample_idx": int(payload.get("sample_idx", 0)),
        "sampling_rate_hz": _float_value(payload, "sampling_rate_hz"),
        "channel_count": len(channels),
        "channels": channels,
        "quality": "ok",
        "ts": str(payload.get("ts") or now_iso()),
    }


def on_connect(client_: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    """Subscribe to raw EEG rows after the MQTT connection opens."""
    logger.info("Connected to MQTT | host=%s | port=%s | rc=%s", MQTT_HOST, MQTT_PORT, reason_code)
    client_.subscribe(RAW_TOPIC, qos=QOS)
    logger.info("Subscribed to raw topic: %s", RAW_TOPIC)
    logger.info("Publishing clean rows to: %s", CLEAN_TOPIC)


def on_message(client_: mqtt.Client, userdata, msg) -> None:
    """Clean one raw MQTT message and publish it to the clean topic."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        clean = clean_payload(payload)
        result = client_.publish(CLEAN_TOPIC, json.dumps(clean), qos=QOS)
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            logger.error("Failed to publish EEG clean payload | rc=%s", result.rc)
    except Exception as exc:
        logger.warning("Dropped EEG raw message | topic=%s | error=%s", msg.topic, exc)


def main() -> None:
    """Run the cleaner forever, reconnecting after broker errors."""
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info("Connecting to MQTT | host=%s | port=%s", MQTT_HOST, MQTT_PORT)
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as exc:
            logger.error("EEG cleaner loop failed; retrying in 3s | error=%s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
