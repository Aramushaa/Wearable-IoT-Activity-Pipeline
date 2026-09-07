"""Entrypoint for replaying Siddha IMU rows to MQTT."""

from __future__ import annotations

import logging
import time
from typing import Optional

from .config import settings
from .dataset_loader import SiddhaDatasetLoader, SensorSample
from .publisher import MqttPublisher


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)


def compute_sleep_seconds(
    previous_sample: Optional[SensorSample],
    current_sample: SensorSample,
    replay_mode: str,
    replay_speed: float,
) -> float:
    """
    Compute how long the simulator should wait before publishing the current sample.

    Why this function exists:
    - keeps replay timing logic separate from the main loop
    - makes behavior easier to test and reason about
    - supports both deterministic real-time replay and faster replay
    """
    if previous_sample is None:
        return 0.0

    if replay_mode == "fast":
        return 0.0

    delta = current_sample.dataset_ts - previous_sample.dataset_ts

    # If the dataset resets to a smaller timestamp because a new recording starts,
    # we should not sleep a negative amount.
    if delta <= 0:
        return 0.0

    if replay_speed <= 0:
        raise ValueError("replay_speed must be > 0")

    return delta / replay_speed


def main() -> None:
    """Load the dataset, connect to MQTT, and publish samples in order."""
    logger.info("Starting Siddha sensor simulator")

    logger.info(
        "Configuration | dataset_path=%s | replay_mode=%s | replay_speed=%s",
        settings.dataset_path,
        settings.replay_mode,
        settings.replay_speed,
    )

    loader = SiddhaDatasetLoader(settings.dataset_path)

    publisher = MqttPublisher(
        host=settings.mqtt_broker_host,
        port=settings.mqtt_broker_port,
        topic_prefix=settings.mqtt_topic_prefix,
        qos=settings.mqtt_qos,
        wait_for_publish=settings.mqtt_wait_for_publish,
    )

    while True:
        try:
            publisher.connect()
            logger.info(
                "Connected to MQTT broker | host=%s | port=%s",
                settings.mqtt_broker_host,
                settings.mqtt_broker_port,
            )
            break
        except Exception as e:
            logger.warning("Broker not ready, retry in 3s: %s", e)
            time.sleep(3)

    previous_sample: Optional[SensorSample] = None
    published_count = 0

    try:
        while True:
            for sample in loader.iter_samples(
                device_filter=settings.default_device_filter,
                activity_filter=settings.default_activity_filter,
                recording_id_filter=settings.default_recording_id_filter,
            ):
                sleep_seconds = compute_sleep_seconds(
                    previous_sample=previous_sample,
                    current_sample=sample,
                    replay_mode=settings.replay_mode,
                    replay_speed=settings.replay_speed,
                )

                if sleep_seconds > 0:
                    time.sleep(sleep_seconds)

                publisher.publish_sample(sample)
                published_count += 1

                if published_count % 100 == 0:
                    logger.info(
                        "Published %s samples | last_device=%s | last_recording=%s | last_dataset_ts=%.3f",
                        published_count,
                        sample.device,
                        sample.recording_id,
                        sample.dataset_ts,
                    )

                previous_sample = sample

            logger.info("Dataset pass complete | total_samples=%s", published_count)

            if not settings.loop_forever:
                break

            logger.info("Restarting replay because loop_forever=true")
            previous_sample = None

    except KeyboardInterrupt:
        logger.warning("Simulator interrupted by user")

    finally:
        publisher.disconnect()
        logger.info("Disconnected from MQTT broker")


if __name__ == "__main__":
    main()
