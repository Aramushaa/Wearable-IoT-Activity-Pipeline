"""MQTT publisher for live HAR prediction messages."""

from __future__ import annotations

import json
import logging

import paho.mqtt.client as mqtt

from .config import settings

logger = logging.getLogger(__name__)


class PredictionPublisher:
    """Own the MQTT connection used to publish live prediction payloads."""

    def __init__(self) -> None:
        """Connect once and keep the paho network loop running."""
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id="har-prediction-publisher")
        self.client.connect(settings.mqtt_host, settings.mqtt_port, 60)
        self.client.loop_start()
        logger.info(
            "Prediction MQTT publisher connected | host=%s | port=%s | topic=%s",
            settings.mqtt_host,
            settings.mqtt_port,
            settings.mqtt_prediction_topic,
        )

    def publish(self, payload: dict) -> None:
        """Publish one HAR prediction payload to the configured topic."""
        result = self.client.publish(
            settings.mqtt_prediction_topic,
            json.dumps(payload),
            qos=settings.mqtt_qos,
        )
        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(f"Failed to publish HAR prediction: rc={result.rc}")
