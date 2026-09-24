"""Live MQTT streaming mode for HAR inference."""

from __future__ import annotations

import json
import logging
import time
from collections import deque
from concurrent.futures import Future, ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Any

import paho.mqtt.client as mqtt

from .config import settings
from .mqtt_publisher import PredictionPublisher
from .windowing import window_to_model_input
from .live_preprocessing import WatchPreprocessor
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
        self.watch_preprocessors = {}
        self.buffers: dict[tuple[str, str], deque[dict[str, Any]]] = {}
        self.prediction_publisher = PredictionPublisher()
        self.prediction_write_executor = ThreadPoolExecutor(
            max_workers=1,
            thread_name_prefix="har-influx-writer",
        )
        self.prediction_write_future: Future | None = None
        self.last_prediction_write_monotonic = float("-inf")
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
        if row.get("source") == "metawear" and settings.live_watch_preprocessing:
            processor = self.watch_preprocessors.setdefault(key, WatchPreprocessor())
            rows, reset = processor.push(row)
            if reset:
                self.buffers.pop(key, None)
            for prepared in rows:
                self._add_prepared_row(key, prepared)
        else:
            self._add_prepared_row(key, row)

    def _add_prepared_row(self, key, row):
        """Window rows only after live sensor conversion and resampling."""
        buffer = self.buffers.setdefault(key, deque())
        buffer.append(row)

        if len(buffer) < settings.window_size:
            return

        window = list(buffer)[: settings.window_size]
        self.evaluate_window(window)

        # Apply stride by removing N rows after prediction.
        remove_count = min(settings.live_window_stride, len(buffer))
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
            "window_stride": settings.live_window_stride,
            "ts": metadata["prediction_ts"],
        }
        live_payload["preprocessing"] = (
            "metawear_siddha_20hz" if settings.live_watch_preprocessing
            and window[0].get("source") == "metawear" else "none"
        )
        self.prediction_publisher.publish(live_payload)
        persisted = self._persist_prediction_async(
            device=metadata["device"],
            recording_id=metadata["recording_id"],
            prediction=prediction,
            confidence=confidence,
            metadata=metadata,
        )

        if persisted:
            logger.info(
                "Live prediction | device=%s | recording_id=%s | predicted=%s | confidence=%.2f | start_ts=%s | end_ts=%s",
                metadata["device"],
                metadata["recording_id"],
                prediction,
                confidence,
                metadata["start_dataset_ts"],
                metadata["end_dataset_ts"],
            )

    def _persist_prediction_async(self, **prediction) -> bool:
        """Persist at a limited rate without blocking the MQTT callback."""
        if not hasattr(self, "prediction_write_executor"):
            self.prediction_write_executor = ThreadPoolExecutor(
                max_workers=1,
                thread_name_prefix="har-influx-writer",
            )
            self.prediction_write_future = None
            self.last_prediction_write_monotonic = float("-inf")

        now = time.monotonic()
        if self.prediction_write_future is not None and not self.prediction_write_future.done():
            return False
        if now - self.last_prediction_write_monotonic < settings.live_persistence_interval_seconds:
            return False

        self.last_prediction_write_monotonic = now
        self.prediction_write_future = self.prediction_write_executor.submit(
            write_prediction_point,
            **prediction,
        )
        self.prediction_write_future.add_done_callback(self._log_prediction_write_error)
        return True

    @staticmethod
    def _log_prediction_write_error(future: Future) -> None:
        """Surface background storage failures without stopping live MQTT."""
        try:
            future.result()
        except Exception:
            logger.exception("Background Influx prediction write failed")

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
