"""Window-building utilities shared by HAR polling and live modes."""

from __future__ import annotations

from collections import defaultdict
from typing import DefaultDict, Iterable


def group_rows_by_device_and_recording(rows: Iterable[dict]) -> dict[tuple[str, str], list[dict]]:
    """Group IMU rows by their stream identity."""
    groups: DefaultDict[tuple[str, str], list[dict]] = defaultdict(list)

    for row in rows:
        device = str(row.get("device", "unknown"))
        recording_id = str(row.get("recording_id", "unknown"))
        groups[(device, recording_id)].append(row)

    return dict(groups)


def build_sliding_windows(
    rows: list[dict],
    window_size: int,
    stride: int,
) -> list[list[dict]]:
    """Build fixed-size sliding windows from ordered IMU rows."""
    if window_size <= 0:
        raise ValueError("window_size must be > 0")
    if stride <= 0:
        raise ValueError("stride must be > 0")

    windows: list[list[dict]] = []

    if len(rows) < window_size:
        return windows

    for start in range(0, len(rows) - window_size + 1, stride):
        end = start + window_size
        windows.append(rows[start:end])

    return windows


def window_to_model_input(window: list[dict]) -> dict:
    """Convert a clean IMU window into the model input structure."""
    if not window:
        raise ValueError("window cannot be empty")

    first = window[0]
    last = window[-1]

    accelerometer = {
        "x": [float(row["acc_x"]) for row in window],
        "y": [float(row["acc_y"]) for row in window],
        "z": [float(row["acc_z"]) for row in window],
    }

    gyroscope = {
        "x": [float(row["gyro_x"]) for row in window],
        "y": [float(row["gyro_y"]) for row in window],
        "z": [float(row["gyro_z"]) for row in window],
    }

    return {
        "accelerometer": accelerometer,
        "gyroscope": gyroscope,
        "metadata": {
            "device": str(first.get("device")),
            "recording_id": str(first.get("recording_id")),
            "activity_gt": str(first.get("activity_gt")),
            "start_dataset_ts": float(first.get("dataset_ts")),
            "end_dataset_ts": float(last.get("dataset_ts")),
            "window_size": len(window),
        },
    }
