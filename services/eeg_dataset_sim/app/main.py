"""Entrypoint for replaying EEG dataset samples to MQTT."""

from __future__ import annotations

import logging
import time
from typing import Optional

from .config import (
    CHANNEL_LIMIT,
    DATASET_PATH,
    DOWNSAMPLE_HZ,
    MAX_SECONDS,
    MQTT_HOST,
    MQTT_PORT,
    MQTT_QOS,
    RAW_TOPIC,
    REPLAY_SPEED,
    STARTUP_DELAY_SECONDS,
    SUBJECT,
    TASK,
)
from .dataset_loader import EegDatasetLoader, EegSample
from .publisher import MqttPublisher

logging.basicConfig(level=logging.INFO, format="%(asctime)s | %(levelname)s | %(message)s")
logger = logging.getLogger(__name__)


def sleep_seconds(previous: Optional[EegSample], current: EegSample) -> float:
    """Preserve recording timing between adjacent EEG samples."""
    if previous is None:
        return 0.0
    if REPLAY_SPEED <= 0:
        raise ValueError("EEG_REPLAY_SPEED must be > 0")
    delta = current.sensor_ts - previous.sensor_ts
    return max(delta, 0.0) / REPLAY_SPEED


def main() -> None:
    """Load EEG samples, connect to MQTT, and replay them with timing."""
    logger.info(
        "Starting EEG dataset simulator | dataset=%s | subject=%s | task=%s | max_seconds=%s",
        DATASET_PATH,
        SUBJECT,
        TASK,
        MAX_SECONDS,
    )
    loader = EegDatasetLoader(
        dataset_path=DATASET_PATH,
        subject=SUBJECT,
        task=TASK,
        max_seconds=MAX_SECONDS,
        channel_limit=CHANNEL_LIMIT,
        downsample_hz=DOWNSAMPLE_HZ,
    )
    publisher = MqttPublisher(MQTT_HOST, MQTT_PORT, RAW_TOPIC, MQTT_QOS)

    while True:
        try:
            publisher.connect()
            logger.info("Connected to MQTT | host=%s | port=%s | topic=%s", MQTT_HOST, MQTT_PORT, RAW_TOPIC)
            break
        except Exception as exc:
            logger.warning("Broker not ready, retrying in 3s | error=%s", exc)
            time.sleep(3)

    if STARTUP_DELAY_SECONDS > 0:
        logger.info("Waiting before replay | startup_delay_seconds=%s", STARTUP_DELAY_SECONDS)
        time.sleep(STARTUP_DELAY_SECONDS)

    previous: Optional[EegSample] = None
    count = 0
    try:
        for sample in loader.iter_samples():
            delay = sleep_seconds(previous, sample)
            if delay > 0:
                time.sleep(delay)
            publisher.publish_sample(sample)
            count += 1
            if count % 100 == 0:
                logger.info("Published EEG samples | count=%s | sensor_ts=%.3f", count, sample.sensor_ts)
            previous = sample
    finally:
        publisher.disconnect()
        logger.info("EEG replay complete | samples=%s", count)


if __name__ == "__main__":
    main()
