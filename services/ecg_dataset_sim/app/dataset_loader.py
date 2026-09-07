"""OpenNeuro BrainVision ECG loader used by the dataset replay service."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import mne


@dataclass(frozen=True)
class EcgSample:
    """One ECG sample at a sensor timestamp."""

    source: str
    device: str
    subject: str
    task: str
    recording_id: str
    sensor_ts: float
    sample_idx: int
    sampling_rate_hz: float
    ecg_value: float
    unit: str


class EcgDatasetLoader:
    """Load the good ECG channel from a BrainVision recording."""

    def __init__(
        self,
        dataset_path: str,
        subject: str,
        task: str,
        max_seconds: float,
        downsample_hz: float,
    ):
        self.dataset_path = Path(dataset_path)
        self.subject = subject
        self.task = task
        self.max_seconds = max_seconds
        self.downsample_hz = downsample_hz
        self.recording_id = f"{subject}_task-{task}"

    @property
    def eeg_dir(self) -> Path:
        """OpenNeuro stores ECG alongside EEG in the subject `eeg` folder."""
        return self.dataset_path / self.subject / "eeg"

    @property
    def vhdr_path(self) -> Path:
        """BrainVision header path used by MNE to load the recording."""
        return self.eeg_dir / f"{self.recording_id}_eeg.vhdr"

    @property
    def channels_path(self) -> Path:
        """BIDS channels table used to locate the ECG channel."""
        return self.eeg_dir / f"{self.recording_id}_channels.tsv"

    def _load_ecg_channel_name(self) -> str:
        """Return the first good ECG channel from the BIDS channels TSV."""
        if not self.channels_path.exists():
            raise FileNotFoundError(f"Channels TSV not found: {self.channels_path}")

        with self.channels_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                if row.get("type", "").upper() != "ECG":
                    continue
                if row.get("status", "").lower() == "bad":
                    continue
                name = row.get("name", "").strip()
                if name:
                    return name

        raise ValueError(f"No good ECG channel found in {self.channels_path}")

    def load_samples(self) -> list[EcgSample]:
        """Load, crop, optionally downsample, and materialize ECG samples."""
        if self.downsample_hz <= 0:
            raise ValueError("ECG_DOWNSAMPLE_HZ must be > 0")
        if self.max_seconds <= 0:
            raise ValueError("ECG_MAX_SECONDS must be > 0")
        if not self.vhdr_path.exists():
            raise FileNotFoundError(f"BrainVision header not found: {self.vhdr_path}")

        channel_name = self._load_ecg_channel_name()
        raw = mne.io.read_raw_brainvision(self.vhdr_path, preload=False, verbose="ERROR")
        raw.pick([channel_name])
        raw.crop(tmin=0.0, tmax=self.max_seconds, include_tmax=False)
        raw.load_data(verbose="ERROR")

        if self.downsample_hz < float(raw.info["sfreq"]):
            raw.resample(self.downsample_hz, verbose="ERROR")

        data = raw.get_data()[0]
        sfreq = float(raw.info["sfreq"])
        samples: list[EcgSample] = []

        for sample_idx, value in enumerate(data):
            sensor_ts = sample_idx / sfreq
            samples.append(
                EcgSample(
                    source="openneuro_ds006848",
                    device="ecg",
                    subject=self.subject,
                    task=self.task,
                    recording_id=self.recording_id,
                    sensor_ts=sensor_ts,
                    sample_idx=sample_idx,
                    sampling_rate_hz=sfreq,
                    ecg_value=float(value),
                    unit="V",
                )
            )

        return samples

    def iter_samples(self) -> Iterator[EcgSample]:
        """Yield samples through the same interface as streaming loaders."""
        yield from self.load_samples()
