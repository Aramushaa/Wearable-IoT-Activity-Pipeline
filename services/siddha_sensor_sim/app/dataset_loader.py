"""Dataset loader for the Siddha human-activity IMU replay."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Optional

import pandas as pd


@dataclass
class SensorSample:
    """Canonical IMU sample published by the Siddha simulator."""

    device: str
    activity_gt: str
    recording_id: str
    dataset_ts: float
    sample_idx: int
    acc_x: float
    acc_y: float
    acc_z: float
    gyro_x: float
    gyro_y: float
    gyro_z: float

class SiddhaDatasetLoader:
    """
    Loads Siddha dataset rows from a Parquet file and yields them
    in deterministic order: recording_id, then timestamp.

    Why this class exists:
    - separates dataset parsing from MQTT publishing
    - keeps replay deterministic and reproducible
    - makes debugging easier before adding transport logic
    """

    REQUIRED_COLUMNS = {
        "device",
        "activity",
        "id",
        "gyro_x",
        "gyro_y",
        "gyro_z",
        "acc_x",
        "acc_y",
        "acc_z",
        "timestamp",
    }

    def __init__(self, dataset_path: str):
        """Keep the path as a `Path` object for validation and loading."""
        self.dataset_path = Path(dataset_path)

    def load_dataframe(self) -> pd.DataFrame:
        """
        Load the Siddha dataset from a Parquet file and validate required columns.
        """
        if not self.dataset_path.exists():
            raise FileNotFoundError(f"Dataset file not found: {self.dataset_path}")

        suffix = self.dataset_path.suffix.lower()
        if suffix not in {".parquet", ".pq"}:
            raise ValueError(
                f"Unsupported dataset format: {suffix}. Expected a Parquet file."
            )

        df = pd.read_parquet(self.dataset_path)

        missing = self.REQUIRED_COLUMNS - set(df.columns)
        if missing:
            raise ValueError(
                f"Dataset is missing required columns: {sorted(missing)}"
            )

        return df

    def iter_samples(
        self,
        device_filter: Optional[str] = None,
        activity_filter: Optional[str] = None,
        recording_id_filter: Optional[str] = None,
    ) -> Iterator[SensorSample]:
        """
        Yield rows ordered by recording_id and timestamp.

        Optional filters are useful for:
        - debugging a single device
        - replaying only one activity
        - testing a single recording sequence
        """
        df = self.load_dataframe()

        if device_filter is not None:
            df = df[df["device"] == device_filter]

        if activity_filter is not None:
            df = df[df["activity"] == activity_filter]

        if recording_id_filter is not None:
            df = df[df["id"].astype(str) == str(recording_id_filter)]

        # Keep a stable original order fallback
        df = df.reset_index(drop=False).rename(columns={"index": "source_row"})

        # Deterministic order for duplicate handling
        df = df.sort_values(
            by=["id", "device", "timestamp", "activity", "source_row"],
            ascending=[True, True, True, True, True],
        )

        # Explicit duplicate rank inside each logical timestamp group
        df["sample_idx"] = (
            df.groupby(["device", "id", "activity", "timestamp"]).cumcount()
        )

        # Replay order stays deterministic
        df = df.sort_values(
            by=["id", "device", "timestamp", "sample_idx"],
            ascending=[True, True, True, True],
        )

        for _, row in df.iterrows():
            activity = str(row["activity"])
            raw_id = str(row["id"])

            yield SensorSample(
                device=str(row["device"]),
                activity_gt=activity,
                recording_id=f"{activity}_{raw_id}",
                dataset_ts=float(row["timestamp"]),
                sample_idx=int(row["sample_idx"]),
                acc_x=float(row["acc_x"]),
                acc_y=float(row["acc_y"]),
                acc_z=float(row["acc_z"]),
                gyro_x=float(row["gyro_x"]),
                gyro_y=float(row["gyro_y"]),
                gyro_z=float(row["gyro_z"]),
            )
