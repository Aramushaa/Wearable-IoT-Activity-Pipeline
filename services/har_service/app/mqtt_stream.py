"""Live MQTT streaming mode for HAR inference."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from .config import settings
from .mqtt_publisher import PredictionPublisher
from .windowing import window_to_model_input
from .writer import write_prediction_point

logger = logging.getLogger(__name__)


def now_iso() -> str:
    """Return a compact UTC timestamp with a trailing Z."""
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


class LiveHarMqttService:
    """
    Phase 4 real-time HAR path.

    It consumes canonical clean IMU rows from MQTT, keeps a per-stream sliding
    window in memory, runs ONNX inference when a window is complete, writes the
    prediction to InfluxDB, and republishes the prediction to MQTT for live UI.
    """

    def __init__(self, inference) -> None:
        """Create the MQTT subscriber and prediction publisher."""
        self.inference = inference
        self.buffers: dict[tuple[str, str], deque[dict[str, Any]]] = {}
        self.prediction_publisher = PredictionPublisher()
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="har-service-live")
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message

    def on_connect(self, client, userdata, flags, reason_code, properties=None) -> None:
        """Subscribe to clean IMU rows after the broker connection opens."""
        logger.info(
            "HAR MQTT mode connected | host=%s | port=%s | rc=%s",
            settings.mqtt_host,
            settings.mqtt_port,
            reason_code,
        )
        client.subscribe(settings.mqtt_topic, qos=settings.mqtt_qos)
        logger.info("HAR subscribed to clean IMU topic: %s", settings.mqtt_topic)

    def validate_clean_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """Validate and normalize the clean IMU row contract."""
        required = {
            "device",
            "recording_id",
            "dataset_ts",
            "sample_idx",
            "acc_x",
            "acc_y",
            "acc_z",
            "gyro_x",
            "gyro_y",
            "gyro_z",
        }
        missing = required - set(row.keys())
        if missing:
            raise ValueError(f"missing required fields: {sorted(missing)}")

        # Normalize types early so the windowing/inference code receives the
        # same structure as the DB polling path.
        row["device"] = str(row["device"])
        row["recording_id"] = str(row["recording_id"])
        row["activity_gt"] = str(row.get("activity_gt", "unknown"))
        row["dataset_ts"] = float(row["dataset_ts"])
        row["sample_idx"] = int(row["sample_idx"])
        for key in ("acc_x", "acc_y", "acc_z", "gyro_x", "gyro_y", "gyro_z"):
            row[key] = float(row[key])
        return row

    def on_message(self, client, userdata, msg) -> None:
        """Decode one clean IMU MQTT message and append it to its stream buffer."""
        try:
            row = json.loads(msg.payload.decode("utf-8"))
            row = self.validate_clean_row(row)
            self.add_row(row)
        except Exception as exc:
            logger.warning("Dropped clean IMU row | topic=%s | error=%s", msg.topic, exc)

    def add_row(self, row: dict[str, Any]) -> None:
        """Add one row to a per-stream buffer and infer when a window is ready."""
        key = (row["device"], row["recording_id"])
        buffer = self.buffers.setdefault(key, deque())
        buffer.append(row)

        if len(buffer) < settings.window_size:
            return

        window = list(buffer)[: settings.window_size]
        self.evaluate_window(window)

        # Apply stride by removing N rows after prediction.
        remove_count = min(settings.window_stride, len(buffer))
        for _ in range(remove_count):
            buffer.popleft()

    def evaluate_window(self, window: list[dict[str, Any]]) -> None:
        """Run inference for a complete live window and publish the result."""
        model_input = window_to_model_input(window)
        prediction_details = self.inference.predict_details(model_input)
        metadata = model_input["metadata"]

        # Use wall-clock time for live prediction points. Otherwise Grafana's
        # "last 5 minutes" dashboard would not show real-time points.
        metadata["prediction_epoch_ns"] = time.time_ns()
        metadata["prediction_ts"] = now_iso()

        prediction = prediction_details["predicted_label"]
        confidence = float(prediction_details["confidence"])

        write_prediction_point(
            device=metadata["device"],
            recording_id=metadata["recording_id"],
            prediction=prediction,
            confidence=confidence,
            metadata=metadata,
        )

        live_payload = {
            "source": "har-service",
            "device": metadata["device"],
            "recording_id": metadata["recording_id"],
            "model_name": settings.model_name,
            "predicted_label": prediction,
            "confidence": confidence,
            "top_k": prediction_details.get("top_k", []),
            "activity_gt": metadata["activity_gt"],
            "window_start_dataset_ts": metadata["start_dataset_ts"],
            "window_end_dataset_ts": metadata["end_dataset_ts"],
            "window_size": metadata["window_size"],
            "window_stride": settings.window_stride,
            "ts": metadata["prediction_ts"],
        }
        self.prediction_publisher.publish(live_payload)

        logger.info(
            "Live prediction | device=%s | recording_id=%s | predicted=%s | confidence=%.2f | start_ts=%s | end_ts=%s",
            metadata["device"],
            metadata["recording_id"],
            prediction,
            confidence,
            metadata["start_dataset_ts"],
            metadata["end_dataset_ts"],
        )

    def run(self) -> None:
        """Run the live MQTT service forever, reconnecting after failures."""
        while True:
            try:
                logger.info(
                    "Starting HAR MQTT stream mode | input_topic=%s | prediction_topic=%s",
                    settings.mqtt_topic,
                    settings.mqtt_prediction_topic,
                )
                self.client.connect(settings.mqtt_host, settings.mqtt_port, 60)
                self.client.loop_forever()
            except Exception as exc:
                logger.exception("HAR MQTT stream failed; retrying in 3s | error=%s", exc)
                time.sleep(3)
