"""OpenNeuro BrainVision EEG loader used by the dataset replay service."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import mne


@dataclass(frozen=True)
class EegSample:
    """One EEG sample with all selected channel values at a sensor timestamp."""

    source: str
    device: str
    subject: str
    task: str
    recording_id: str
    sensor_ts: float
    sample_idx: int
    sampling_rate_hz: float
    channels: dict[str, float]


class EegDatasetLoader:
    """Load EEG channels from a BrainVision recording into publishable samples."""

    def __init__(
        self,
        dataset_path: str,
        subject: str,
        task: str,
        max_seconds: float,
        channel_limit: int,
        downsample_hz: float,
    ):
        self.dataset_path = Path(dataset_path)
        self.subject = subject
        self.task = task
        self.max_seconds = max_seconds
        self.channel_limit = channel_limit
        self.downsample_hz = downsample_hz
        self.recording_id = f"{subject}_task-{task}"

    @property
    def eeg_dir(self) -> Path:
        """Directory containing BrainVision files for the configured subject."""
        return self.dataset_path / self.subject / "eeg"

    @property
    def vhdr_path(self) -> Path:
        """BrainVision header path used by MNE to load the recording."""
        return self.eeg_dir / f"{self.recording_id}_eeg.vhdr"

    @property
    def channels_path(self) -> Path:
        """BIDS channels table used to select good EEG channels only."""
        return self.eeg_dir / f"{self.recording_id}_channels.tsv"

    def _load_eeg_channel_names(self) -> list[str]:
        """Read good EEG channel names from the BIDS channels TSV."""
        if not self.channels_path.exists():
            raise FileNotFoundError(f"Channels TSV not found: {self.channels_path}")

        names: list[str] = []
        with self.channels_path.open("r", encoding="utf-8-sig", newline="") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                if row.get("type", "").upper() != "EEG":
                    continue
                if row.get("status", "").lower() == "bad":
                    continue
                name = row.get("name", "").strip()
                if name:
                    names.append(name)

        if not names:
            raise ValueError(f"No good EEG channels found in {self.channels_path}")

        return names[: self.channel_limit]

    def load_samples(self) -> list[EegSample]:
        """Load, crop, optionally downsample, and materialize EEG samples."""
        if self.downsample_hz <= 0:
            raise ValueError("EEG_DOWNSAMPLE_HZ must be > 0")
        if self.max_seconds <= 0:
            raise ValueError("EEG_MAX_SECONDS must be > 0")
        if not self.vhdr_path.exists():
            raise FileNotFoundError(f"BrainVision header not found: {self.vhdr_path}")

        channel_names = self._load_eeg_channel_names()
        raw = mne.io.read_raw_brainvision(self.vhdr_path, preload=False, verbose="ERROR")
        raw.pick(channel_names)
        raw.crop(tmin=0.0, tmax=self.max_seconds, include_tmax=False)
        raw.load_data(verbose="ERROR")

        if self.downsample_hz < float(raw.info["sfreq"]):
            raw.resample(self.downsample_hz, verbose="ERROR")

        data = raw.get_data()
        sfreq = float(raw.info["sfreq"])
        samples: list[EegSample] = []

        for sample_idx in range(data.shape[1]):
            sensor_ts = sample_idx / sfreq
            channels = {
                name: float(data[channel_idx, sample_idx])
                for channel_idx, name in enumerate(raw.ch_names)
            }
            samples.append(
                EegSample(
                    source="openneuro_ds006848",
                    device="eeg",
                    subject=self.subject,
                    task=self.task,
                    recording_id=self.recording_id,
                    sensor_ts=sensor_ts,
                    sample_idx=sample_idx,
                    sampling_rate_hz=sfreq,
                    channels=channels,
                )
            )

        return samples

    def iter_samples(self) -> Iterator[EegSample]:
        """Yield samples through the same interface as streaming loaders."""
        yield from self.load_samples()
