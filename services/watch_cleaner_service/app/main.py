"""Clean raw MetaWear accelerometer/gyroscope MQTT events into IMU rows."""

from __future__ import annotations

import json
import logging
import math
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from .config import (
    CLEAN_TOPIC,
    DEFAULT_ACTIVITY_GT,
    MAX_ABS_ACC,
    MAX_ABS_GYRO,
    MAX_PAIR_AGE_SECONDS,
    MQTT_CLIENT_ID,
    MQTT_HOST,
    MQTT_PORT,
    QOS,
    RAW_TOPIC,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


@dataclass
class RawSensorSample:
    """One raw MetaWear sensor notification after JSON parsing."""

    sensor: str
    sensor_ts: float
    x: float
    y: float
    z: float
    wall_ts: str
    source: str
    device: str
    recording_id: str
    sampling_rate_hz: float


# Pairing state is keyed by `(device, recording_id)` so multiple watches or
# sessions can be processed by the same cleaner without mixing samples.
latest_acc: dict[tuple[str, str], RawSensorSample] = {}
clean_sample_idx: dict[tuple[str, str], int] = {}

# Observability counters are intentionally simple module-level values because
# this service has one MQTT callback loop per process.
_COUNTERS = {
    "raw_acc_received": 0,
    "raw_gyro_received": 0,
    "clean_rows_published": 0,
    "dropped_missing_acc": 0,
    "dropped_stale_pair": 0,
    "dropped_invalid_value": 0,
}

client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=MQTT_CLIENT_ID)


def now_iso() -> str:
    """Return a compact UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _as_float(payload: dict[str, Any], key: str) -> float:
    """Read a required float from a raw watch payload."""
    value = payload.get(key)
    if value is None:
        raise ValueError(f"missing field: {key}")
    return float(value)


def parse_raw_payload(payload: dict[str, Any]) -> RawSensorSample:
    """Parse raw MetaWear JSON into the internal sample model."""
    sensor = str(payload.get("sensor", "")).strip().lower()
    if sensor not in {"acc", "gyro"}:
        raise ValueError(f"unsupported sensor type: {sensor!r}")

    return RawSensorSample(
        sensor=sensor,
        sensor_ts=_as_float(payload, "sensor_ts"),
        x=_as_float(payload, "x"),
        y=_as_float(payload, "y"),
        z=_as_float(payload, "z"),
        wall_ts=str(payload.get("ts") or now_iso()),
        source=str(payload.get("source", "metawear")),
        device=str(payload.get("device", "watch")),
        recording_id=str(payload.get("recording_id", "unknown")),
        sampling_rate_hz=float(payload.get("sampling_rate_hz", 25)),
    )


def validate_sample(sample: RawSensorSample) -> None:
    """Reject non-finite values and physically implausible sensor spikes."""
    bound = MAX_ABS_ACC if sample.sensor == "acc" else MAX_ABS_GYRO
    for axis, value in {"x": sample.x, "y": sample.y, "z": sample.z}.items():
        if not math.isfinite(value):
            raise ValueError(
                f"{sample.sensor}.{axis} is not finite: {value}"
            )
        if abs(value) > bound:
            raise ValueError(
                f"{sample.sensor}.{axis} out of range: {value} > allowed abs {bound}"
            )


def build_clean_payload(acc: RawSensorSample, gyro: RawSensorSample) -> dict[str, Any]:
    """Merge the latest accelerometer sample with a gyroscope sample."""
    key = (gyro.device, gyro.recording_id)
    idx = clean_sample_idx.get(key, 0)
    clean_sample_idx[key] = idx + 1

    # Use the gyro sample timestamp as the canonical row timestamp because we publish
    # one complete row when a gyro sample arrives and the latest acc sample is available.
    sensor_ts = gyro.sensor_ts

    return {
        "source": "metawear",
        "device": gyro.device,
        "recording_id": gyro.recording_id,
        "sensor_ts": sensor_ts,
        # Compatibility with existing Phase 3 ingest/HAR schema.
        "dataset_ts": sensor_ts,
        "sample_idx": idx,
        "acc_x": acc.x,
        "acc_y": acc.y,
        "acc_z": acc.z,
        "gyro_x": gyro.x,
        "gyro_y": gyro.y,
        "gyro_z": gyro.z,
        "activity_gt": DEFAULT_ACTIVITY_GT,
        "sampling_rate_hz": gyro.sampling_rate_hz,
        "quality": "ok",
        # Wall-clock timestamp for real-time database visualization.
        "ts": now_iso(),
    }


def maybe_publish_clean(sample: RawSensorSample) -> None:
    """Store accelerometer samples and publish a clean row for valid gyro pairs."""
    key = (sample.device, sample.recording_id)

    if sample.sensor == "acc":
        _COUNTERS["raw_acc_received"] += 1
        latest_acc[key] = sample
        return

    _COUNTERS["raw_gyro_received"] += 1

    acc = latest_acc.get(key)
    if acc is None:
        _COUNTERS["dropped_missing_acc"] += 1
        logger.debug("Dropping gyro because no ACC sample exists yet | key=%s", key)
        return

    pair_age = abs(sample.sensor_ts - acc.sensor_ts)
    if pair_age > MAX_PAIR_AGE_SECONDS:
        _COUNTERS["dropped_stale_pair"] += 1
        logger.warning(
            "Dropping stale pair | key=%s | pair_age=%.3fs | max=%.3fs",
            key,
            pair_age,
            MAX_PAIR_AGE_SECONDS,
        )
        return

    clean_payload = build_clean_payload(acc, sample)
    result = client.publish(CLEAN_TOPIC, json.dumps(clean_payload), qos=QOS)
    if result.rc != mqtt.MQTT_ERR_SUCCESS:
        logger.error("Failed to publish clean payload | rc=%s", result.rc)
    else:
        _COUNTERS["clean_rows_published"] += 1


def on_connect(client_: mqtt.Client, userdata, flags, reason_code, properties=None) -> None:
    """Subscribe to raw watch rows after the MQTT connection opens."""
    logger.info("Connected to MQTT | host=%s | port=%s | rc=%s", MQTT_HOST, MQTT_PORT, reason_code)
    client_.subscribe(RAW_TOPIC, qos=QOS)
    logger.info("Subscribed to raw topic: %s", RAW_TOPIC)
    logger.info("Publishing clean rows to: %s", CLEAN_TOPIC)


def on_message(client_: mqtt.Client, userdata, msg) -> None:
    """Parse, validate, pair, and republish one raw watch MQTT message."""
    try:
        payload = json.loads(msg.payload.decode("utf-8"))
        sample = parse_raw_payload(payload)
        validate_sample(sample)
        maybe_publish_clean(sample)
    except ValueError:
        _COUNTERS["dropped_invalid_value"] += 1
        logger.warning("Dropped raw message (invalid value) | topic=%s", msg.topic)
    except Exception as exc:
        logger.warning("Dropped raw message | topic=%s | error=%s", msg.topic, exc)


def main() -> None:
    """Run the watch cleaner forever, reconnecting after broker errors."""
    client.on_connect = on_connect
    client.on_message = on_message

    while True:
        try:
            logger.info("Connecting to MQTT | host=%s | port=%s", MQTT_HOST, MQTT_PORT)
            client.connect(MQTT_HOST, MQTT_PORT, 60)
            client.loop_forever()
        except Exception as exc:
            logger.error("MQTT cleaner loop failed; retrying in 3s | error=%s", exc)
            time.sleep(3)


if __name__ == "__main__":
    main()
