"""MQTT publisher for Siddha IMU replay samples."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import paho.mqtt.client as mqtt

from .dataset_loader import SensorSample


class MqttPublisher:
    """
    Publishes SensorSample objects as MQTT JSON messages.

    Why this class exists:
    - separates MQTT transport logic from dataset loading logic
    - makes topic/payload generation reusable and testable
    - keeps the simulator entrypoint clean
    """

    def __init__(
        self,
        host: str,
        port: int,
        topic_prefix: str,
        qos: int = 0,
        wait_for_publish: bool = False,
    ):
        """Create a publisher with reusable connection and topic settings."""
        self.host = host
        self.port = port
        self.topic_prefix = topic_prefix.rstrip("/")
        self.qos = qos
        self.wait_for_publish = wait_for_publish
        self.client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)

    def connect(self) -> None:
        """
        Connect to the MQTT broker.
        """
        self.client.connect(self.host, self.port, keepalive=60)
        self.client.loop_start()

    def disconnect(self) -> None:
        """
        Cleanly disconnect from the MQTT broker.
        """
        self.client.loop_stop()
        self.client.disconnect()

    def build_topic(self, sample: SensorSample) -> str:
        """
        Build MQTT topic for one sample.

        Example:
        tennis/sensor/phone/events
        """
        return f"{self.topic_prefix}/{sample.device}/events"

    def build_payload(self, sample: SensorSample) -> dict:
        """
        Convert a SensorSample into the JSON payload we want to publish.

        We include both:
        - dataset_ts: original time inside the Siddha recording
        - ts: wall-clock publish timestamp for distributed-system tracing
        """
        return {
            "device": sample.device,
            "recording_id": sample.recording_id,
            "activity_gt": sample.activity_gt,
            "dataset_ts": sample.dataset_ts,
            "sample_idx": sample.sample_idx,
            "acc_x": sample.acc_x,
            "acc_y": sample.acc_y,
            "acc_z": sample.acc_z,
            "gyro_x": sample.gyro_x,
            "gyro_y": sample.gyro_y,
            "gyro_z": sample.gyro_z,
            "ts": datetime.now(timezone.utc).isoformat(),
        }

    def publish_sample(self, sample: SensorSample) -> None:
        """
        Publish one sample to MQTT as JSON.
        """
        topic = self.build_topic(sample)
        payload = self.build_payload(sample)

        result = self.client.publish(
            topic=topic,
            payload=json.dumps(payload),
            qos=self.qos,
        )

        if self.wait_for_publish:
            result.wait_for_publish()

        if result.rc != mqtt.MQTT_ERR_SUCCESS:
            raise RuntimeError(
                f"Failed to publish MQTT message to topic '{topic}', rc={result.rc}"
            )
