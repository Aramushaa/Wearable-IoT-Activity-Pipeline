"""Run the local MetaWear BLE bridge and publish raw sensor samples to MQTT."""

import signal
import time
from datetime import datetime, timezone

from app.metawear_client import MetaWearClient
from app.mqtt_publisher import MQTTPublisher
from app.config import (
    MAC_ADDRESS,
    MQTT_TOPIC,
    DEVICE_NAME,
    RECORDING_ID,
    SAMPLING_RATE_HZ,
)

if not MAC_ADDRESS or MAC_ADDRESS == "YOUR_MAC_ADDRESS_HERE":
    raise RuntimeError("Set METAWEAR_MAC_ADDRESS in .env before starting the bridge")

publisher = MQTTPublisher()
recording_started_at = time.time()
# The bridge publishes raw per-sensor samples; pairing happens in the cleaner.
raw_sample_idx = {"acc": 0, "gyro": 0}

# Debug counters: print rate once per second instead of printing every sample.
counts = {"acc": 0, "gyro": 0}
last_rate_print = time.time()


def now_iso() -> str:
    """Return a compact UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def my_function(sensor, timestamp, x, y, z):
    """
    Callback called by MetaWearClient for each raw ACC/GYRO notification.

    Important Phase 4 design:
    - The bridge is only a BLE -> MQTT protocol adapter.
    - It does NOT merge accelerometer and gyroscope.
    - The data_cleaner_service owns pairing, validation, and canonical schema.
    """
    global last_rate_print

    if sensor not in ("acc", "gyro"):
        return

    sensor_ts = time.time() - recording_started_at
    sample_idx = raw_sample_idx[sensor]
    raw_sample_idx[sensor] += 1

    payload = {
        "source": "metawear",
        "device": DEVICE_NAME,
        "recording_id": RECORDING_ID,
        "sensor": sensor,
        "sensor_ts": sensor_ts,
        "metawear_epoch_ms": int(timestamp),
        "sample_idx": sample_idx,
        "x": float(x),
        "y": float(y),
        "z": float(z),
        "sampling_rate_hz": SAMPLING_RATE_HZ,
        "ts": now_iso(),
    }

    publisher.publish(MQTT_TOPIC, payload)

    counts[sensor] += 1
    now = time.time()
    if now - last_rate_print >= 1.0:
        print("Raw publish rate per second:", counts)
        counts["acc"] = 0
        counts["gyro"] = 0
        last_rate_print = now


sensor = MetaWearClient(MAC_ADDRESS)
sensor.set_callback(my_function)

# Register SIGINT / SIGTERM so we always disconnect the BLE device cleanly.
def _shutdown_handler(signum, frame):
    """Ask the sampling loop to stop before process termination."""
    sensor.stop_sampling()

signal.signal(signal.SIGINT, _shutdown_handler)
signal.signal(signal.SIGTERM, _shutdown_handler)

print("Connecting to MetaWear...")
try:
    sensor.connect()
    sensor.configure()
    print(f"Streaming RAW MetaWear data to MQTT topic: {MQTT_TOPIC}")
    sensor.start_sampling()
except KeyboardInterrupt:
    print("Stopping bridge (KeyboardInterrupt)...")
except Exception as e:
    print(f"Bridge error: {e}")
finally:
    print("Disconnecting MetaWear sensor...")
    try:
        sensor.disconnect()
    except Exception as disc_err:
        print(f"Error during disconnect: {disc_err}")
    print("MetaWear bridge shut down.")
