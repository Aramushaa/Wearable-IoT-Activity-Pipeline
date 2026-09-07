"""MQTT subscriber for the ingest service.

The subscriber keeps a small in-memory event buffer for debug endpoints and
routes recognized payloads into the asynchronous InfluxDB writer.
"""

import json
import threading
import time
from collections import deque
from typing import Any, Deque, Dict, Optional
from .utils.time_utils import now_iso

import paho.mqtt.client as mqtt

from .config import (
    MQTT_HOST,
    MQTT_PORT,
    SUB_TOPICS,
    EVENT_BUFFER_MAX,
    INFLUX_ENABLED,
    INFLUX_WRITE_GENERIC_EVENTS,
)
from .influx import (
    write_ecg_to_influx,
    write_eeg_to_influx,
    write_event_to_influx,
    write_imu_raw_to_influx,
)


# Recent events are stored for `/events?source=memory` so diagnostics still work
# when InfluxDB is disabled or temporarily unavailable.
EVENTS: Deque[Dict[str, Any]] = deque(maxlen=EVENT_BUFFER_MAX)
EVENTS_LOCK = threading.Lock()

mqtt_client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="ingest-service")
mqtt_thread: Optional[threading.Thread] = None




def normalize_event(topic: str, payload_obj: Any) -> Dict[str, Any]:
    """Wrap a decoded MQTT payload in the generic event envelope."""
    ts = payload_obj.get("ts") if isinstance(payload_obj, dict) else None
    return {
        "ts": ts or now_iso(),
        "topic": topic,
        "source": "mqtt",
        "payload": payload_obj,
    }


def on_connect(client, userdata, flags, rc, properties=None):
    """Subscribe to every configured topic after the broker connection opens."""
    print("[MQTT] connected rc=", rc)
    for t in SUB_TOPICS:
        client.subscribe(t, qos=1)
        print("[MQTT] subscribed to:", t, "with QoS 1")


def _enqueue_influx_writes(ev: Dict[str, Any], payload_obj: Any) -> None:
    """
    Prepare and enqueue Influx writes from the MQTT callback thread.

    The actual HTTP write is asynchronous relative to MQTT processing because
    `write_event_to_influx()` and `write_imu_raw_to_influx()` only enqueue line
    protocol for the dedicated background writer thread in `influx.py`.
    """
    try:
        if INFLUX_WRITE_GENERIC_EVENTS:
            write_event_to_influx(ev)

        if not isinstance(payload_obj, dict):
            return

        device = payload_obj.get("device")
        required_imu_fields = {"acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"}
        # Device-specific writers keep biosignals and IMU rows queryable instead
        # of storing everything only as opaque JSON in the generic events table.
        if device == "eeg":
            write_eeg_to_influx(payload_obj)
        elif device == "ecg":
            write_ecg_to_influx(payload_obj)
        elif required_imu_fields.issubset(payload_obj.keys()):
            write_imu_raw_to_influx(payload_obj)
    except Exception as e:
        print("[INFLUX] write error:", e)


def on_message(client, userdata, msg):
    """Decode an MQTT message, save it for diagnostics, and enqueue DB writes."""
    try:
        raw = msg.payload.decode("utf-8", errors="replace")
    except Exception as e:
        print("[MQTT] payload decode error:", e)
        return

    try:
        payload_obj = json.loads(raw)
    except Exception:
        payload_obj = {"_raw": raw, "_note": "non-json payload"}

    ev = normalize_event(msg.topic, payload_obj)

    with EVENTS_LOCK:
        EVENTS.append(ev)

    if INFLUX_ENABLED:
        _enqueue_influx_writes(ev, payload_obj)

def mqtt_worker():
    """Own the reconnect loop for the process-wide MQTT client."""
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    while True:
        try:
            print(f"[MQTT] connecting to {MQTT_HOST}:{MQTT_PORT} ...")
            mqtt_client.connect(MQTT_HOST, MQTT_PORT, 60)
            mqtt_client.loop_forever()
        except Exception as e:
            print("[MQTT] error, retrying in 3s:", e)
            time.sleep(3)


def start_mqtt_thread():
    """Start the MQTT loop in a daemon thread so FastAPI can serve requests."""
    global mqtt_thread
    mqtt_thread = threading.Thread(target=mqtt_worker, daemon=True)
    mqtt_thread.start()


def stop_mqtt():
    """Disconnect the MQTT client during application shutdown."""
    try:
        mqtt_client.disconnect()
    except Exception:
        pass


def get_memory_events(limit: int) -> list[dict]:
    """Return the newest in-memory events without exposing the mutable deque."""
    with EVENTS_LOCK:
        return list(EVENTS)[-limit:]
