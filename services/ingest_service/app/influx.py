"""InfluxDB 3 write/query helpers for the ingest service.

MQTT callbacks call the public `write_*` functions, which build Influx line
protocol and enqueue it. A background writer drains that queue in batches so
short database outages do not block message ingestion.
"""

import json
import math
import threading
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from .utils.time_utils import now_iso
from typing import Any, Deque, Dict, Optional
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import (
    INFLUX_BATCH_SIZE,
    INFLUX_DATABASE,
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_ENABLED,
    INFLUX_FLUSH_INTERVAL_MS,
    INFLUX_HOST,
    INFLUX_IMU_TABLE,
    INFLUX_MAX_QUEUE_SIZE,
    INFLUX_WATCH_IMU_TABLE,
    INFLUX_TABLE,
    INFLUX_TOKEN,
)


MAX_RETRIES = 3


@dataclass
class QueueItem:
    """One line-protocol row plus retry metadata for the writer queue."""

    line: str
    retries: int = 0


# Queue state is module-level because FastAPI and MQTT callbacks share this
# process. All access to `_WRITE_QUEUE` must hold `_QUEUE_LOCK`.
_WRITE_QUEUE: Deque[QueueItem] = deque()
_QUEUE_LOCK = threading.Lock()
_FLUSH_SIGNAL = threading.Event()
_STOP_SIGNAL = threading.Event()
_WRITER_THREAD: Optional[threading.Thread] = None

_FAILED_BATCH_COUNT = 0
_RETRIED_LINE_COUNT = 0
_DROPPED_LINE_COUNT = 0


def iso_to_epoch_nanos(ts: str) -> int:
    """
    Convert ISO timestamp to epoch nanoseconds.
    Handles:
      - "2026-02-10T16:59:10.239950Z"
      - "2026-02-10T16:59:10+00:00"
    """
    ts = ts.replace("Z", "+00:00")
    dt = datetime.fromisoformat(ts)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def parse_topic(topic: str) -> tuple[str, str]:
    """Extract the high-level stream and source id from a tennis MQTT topic."""
    parts = topic.split("/")
    stream = parts[1] if len(parts) > 1 else "unknown"
    source_id = parts[2] if len(parts) > 2 else "unknown"
    return stream, source_id


def _write_lp_v3(line_protocol: str, db: str, precision: str = "s") -> None:
    """Send line protocol to InfluxDB 3 using the HTTP write endpoint."""
    if not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is empty")

    params = urlencode({"db": db, "precision": precision})
    url = f"{INFLUX_HOST}/api/v3/write_lp?{params}"

    req = Request(url, data=line_protocol.encode("utf-8"), method="POST")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")
    req.add_header("Content-Type", "text/plain; charset=utf-8")

    import urllib.error

    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 202, 204):
                raise RuntimeError(f"Influx write failed HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"HTTP Error {e.code}: {e.reason} - Body: {body}")


def _enqueue_line(line: str) -> None:
    """Add a line-protocol row to the bounded writer queue."""
    global _DROPPED_LINE_COUNT

    with _QUEUE_LOCK:
        if len(_WRITE_QUEUE) >= INFLUX_MAX_QUEUE_SIZE:
            _DROPPED_LINE_COUNT += 1
            print(
                f"[INFLUX] CRITICAL: queue full ({INFLUX_MAX_QUEUE_SIZE}), "
                f"dropping line (total dropped: {_DROPPED_LINE_COUNT})"
            )
            return
        _WRITE_QUEUE.append(QueueItem(line=line))
        if len(_WRITE_QUEUE) >= INFLUX_BATCH_SIZE:
            _FLUSH_SIGNAL.set()


def _drain_lines(limit: Optional[int] = None) -> list[QueueItem]:
    """Remove up to `limit` queued rows for one write attempt."""
    with _QUEUE_LOCK:
        if not _WRITE_QUEUE:
            return []

        if limit is None:
            limit = len(_WRITE_QUEUE)

        items: list[QueueItem] = []
        for _ in range(min(limit, len(_WRITE_QUEUE))):
            items.append(_WRITE_QUEUE.popleft())

        return items


def _requeue_failed_items(items: list[QueueItem]) -> None:
    """
    Put retryable items back at the FRONT of the queue so they are not delayed
    behind newer data. Drop items that exceeded MAX_RETRIES.
    """
    global _RETRIED_LINE_COUNT, _DROPPED_LINE_COUNT

    retryable: list[QueueItem] = []
    dropped = 0

    for item in items:
        if item.retries < MAX_RETRIES:
            item.retries += 1
            retryable.append(item)
        else:
            dropped += 1

    if retryable:
        with _QUEUE_LOCK:
            # appendleft reverses order, so we insert in reversed order
            for item in reversed(retryable):
                _WRITE_QUEUE.appendleft(item)
        _RETRIED_LINE_COUNT += len(retryable)
        _FLUSH_SIGNAL.set()

    if dropped > 0:
        _DROPPED_LINE_COUNT += dropped
        print(
            f"[INFLUX] CRITICAL: dropped {dropped} lines after {MAX_RETRIES} retries"
        )


def _flush_lines(items: list[QueueItem]) -> None:
    """Write a drained batch to InfluxDB as a newline-delimited payload."""
    if not items:
        return

    payload = "\n".join(item.line for item in items)
    _write_lp_v3(payload, db=INFLUX_DATABASE, precision="ns")


def _writer_loop() -> None:
    """Batch queued line-protocol rows until shutdown is requested."""
    global _FAILED_BATCH_COUNT

    flush_interval = max(INFLUX_FLUSH_INTERVAL_MS, 1) / 1000.0

    while not _STOP_SIGNAL.is_set():
        _FLUSH_SIGNAL.wait(timeout=flush_interval)
        _FLUSH_SIGNAL.clear()

        while True:
            items = _drain_lines(INFLUX_BATCH_SIZE)
            if not items:
                break

            try:
                _flush_lines(items)
            except Exception as e:
                _FAILED_BATCH_COUNT += 1
                print(f"[INFLUX] batch write error ({len(items)} lines): {e}")
                _requeue_failed_items(items)
                break

    # Final drain on shutdown
    while True:
        items = _drain_lines(INFLUX_BATCH_SIZE)
        if not items:
            break

        try:
            _flush_lines(items)
        except Exception as e:
            _FAILED_BATCH_COUNT += 1
            print(f"[INFLUX] batch write error | lines={len(items)} | error={e}")
            print("[INFLUX] retrying failed batch immediately")
            _requeue_failed_items(items)
            break


def start_influx_writer() -> None:
    """Start the background InfluxDB writer if it is enabled and not running."""
    global _WRITER_THREAD

    if not INFLUX_ENABLED:
        return
    if _WRITER_THREAD and _WRITER_THREAD.is_alive():
        return

    _STOP_SIGNAL.clear()
    _FLUSH_SIGNAL.clear()
    _WRITER_THREAD = threading.Thread(
        target=_writer_loop,
        daemon=True,
        name="influx-writer",
    )
    _WRITER_THREAD.start()


def stop_influx_writer() -> None:
    """Signal the writer thread to flush outstanding rows and exit."""
    global _WRITER_THREAD

    if not _WRITER_THREAD:
        return

    _STOP_SIGNAL.set()
    _FLUSH_SIGNAL.set()
    _WRITER_THREAD.join(timeout=5)
    _WRITER_THREAD = None


def escape_tag_value(value: str) -> str:
    """Escape special characters in an InfluxDB line-protocol tag value."""
    return str(value).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def escape_key(value: str) -> str:
    """Escape a line-protocol measurement, tag key, or field key."""
    return str(value).replace("\\", "\\\\").replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def escape_field_string(value: Any) -> str:
    """Escape a string field value for InfluxDB line protocol."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def _finite_float(value: Any, name: str) -> float:
    """Convert a payload value to a finite float with a field-specific error."""
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite")
    return number


def _biosignal_timestamp(payload: dict) -> int:
    """
    Dataset biosignals should use deterministic dataset time.
    This allows repeated replay of the same subject/task/recording
    to overwrite the same logical points instead of appending duplicates.
    """
    base_epoch_ns = 1704067200_000_000_000
    dataset_ts = float(payload.get("dataset_ts", payload.get("sensor_ts", 0.0)))
    dataset_ts_ns = int(dataset_ts * 1_000_000_000)
    return base_epoch_ns + dataset_ts_ns


def write_event_to_influx(ev: Dict[str, Any]) -> None:
    """Store the raw event envelope as a JSON payload field."""
    if not INFLUX_ENABLED:
        return

    topic = ev.get("topic", "unknown")
    stream, source_id = parse_topic(topic)
    ts_epoch = iso_to_epoch_nanos(ev.get("ts") or now_iso())

    stream_tag = escape_tag_value(stream)
    source_id_tag = escape_tag_value(source_id)

    payload_str = json.dumps(ev.get("payload", {}), ensure_ascii=False)
    escaped_payload = payload_str.replace("\\", "\\\\").replace('"', '\\"')
    line = (
        f'{INFLUX_TABLE},stream={stream_tag},source_id={source_id_tag} '
        f'payload="{escaped_payload}" {ts_epoch}'
    )
    _enqueue_line(line)


def query_influx_sql(sql: str) -> list[dict]:
    """Run a SQL query against InfluxDB 3 and return decoded JSON rows."""
    if not INFLUX_TOKEN:
        raise RuntimeError("INFLUX_TOKEN is empty")

    params = urlencode({"db": INFLUX_DATABASE, "q": sql})
    url = f"{INFLUX_HOST}/api/v3/query_sql?{params}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")

    with urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")
    return json.loads(body)


def get_influx_writer_stats() -> dict:
    """Expose writer queue counters for `/health` and `/stats` endpoints."""
    with _QUEUE_LOCK:
        queue_depth = len(_WRITE_QUEUE)

    return {
        "queue_depth": queue_depth,
        "failed_batch_count": _FAILED_BATCH_COUNT,
        "retried_line_count": _RETRIED_LINE_COUNT,
        "dropped_line_count": _DROPPED_LINE_COUNT,
        "writer_thread_alive": _WRITER_THREAD.is_alive() if _WRITER_THREAD else False,
        "max_retries": MAX_RETRIES,
    }


def write_imu_raw_to_influx(payload: dict) -> None:
    """
    Write structured IMU data into a dedicated measurement (imu_raw).
    """
    if not INFLUX_ENABLED:
        return

    try:
        device = payload.get("device", "unknown")
        recording_id = payload.get("recording_id", "unknown")
        source = payload.get("source", "dataset")
        sample_idx = int(payload.get("sample_idx", 0))

        target_table = (
            INFLUX_WATCH_IMU_TABLE
            if source == "metawear"
            else INFLUX_IMU_TABLE
        )

        acc_x = float(payload["acc_x"])
        acc_y = float(payload["acc_y"])
        acc_z = float(payload["acc_z"])
        gyro_x = float(payload["gyro_x"])
        gyro_y = float(payload["gyro_y"])
        gyro_z = float(payload["gyro_z"])

        dataset_ts = float(payload.get("dataset_ts", 0.0))
        activity_gt = payload.get("activity_gt", "unknown")

        # Dataset replay uses a deterministic synthetic epoch based on dataset_ts.
        # Real watch rows use wall-clock time from the cleaner so Grafana can show
        # them in a live dashboard with a normal "last 5 minutes" time range.
        if source == "metawear" and payload.get("ts"):
            ts_epoch = iso_to_epoch_nanos(str(payload["ts"]))
        else:
            base_epoch_ns = 1704067200_000_000_000
            dataset_ts_ns = int(dataset_ts * 1_000_000_000)
            ts_epoch = base_epoch_ns + dataset_ts_ns

        escaped_activity_gt = (
            str(activity_gt).replace("\\", "\\\\").replace('"', '\\"')
        )

        device_tag = escape_tag_value(device)
        recording_id_tag = escape_tag_value(recording_id)

        line = (
            f"{target_table},device={device_tag},recording_id={recording_id_tag} "
            f"sample_idx={sample_idx}i,"
            f"acc_x={acc_x},acc_y={acc_y},acc_z={acc_z},"
            f"gyro_x={gyro_x},gyro_y={gyro_y},gyro_z={gyro_z},"
            f'dataset_ts={dataset_ts},activity_gt="{escaped_activity_gt}" {ts_epoch}'
        )

        _enqueue_line(line)
    except Exception as e:
        print(f"[Influx IMU] Error: {e}")


def write_eeg_to_influx(payload: dict) -> None:
    """
    Write clean EEG rows into the configured EEG measurement.
    """
    if not INFLUX_ENABLED:
        return

    try:
        channels = payload.get("channels")
        if not isinstance(channels, dict) or not channels:
            raise ValueError("channels must be a non-empty object")

        device = escape_tag_value(payload.get("device", "eeg"))
        subject = escape_tag_value(payload.get("subject", "unknown"))
        task = escape_tag_value(payload.get("task", "unknown"))
        recording_id = escape_tag_value(payload.get("recording_id", "unknown"))
        source = escape_tag_value(payload.get("source", "openneuro_ds006848"))

        sample_idx = int(payload.get("sample_idx", 0))
        dataset_ts = _finite_float(payload.get("dataset_ts", payload.get("sensor_ts", 0.0)), "dataset_ts")
        sensor_ts = _finite_float(payload.get("sensor_ts", dataset_ts), "sensor_ts")
        sampling_rate_hz = _finite_float(payload.get("sampling_rate_hz", 0.0), "sampling_rate_hz")
        channel_count = int(payload.get("channel_count", len(channels)))
        quality = escape_field_string(payload.get("quality", "ok"))

        fields = [
            f"sample_idx={sample_idx}i",
            f"dataset_ts={dataset_ts}",
            f"sensor_ts={sensor_ts}",
            f"sampling_rate_hz={sampling_rate_hz}",
            f"channel_count={channel_count}i",
            f'quality="{quality}"',
        ]

        for name, value in channels.items():
            channel_value = _finite_float(value, f"channels.{name}")
            fields.append(f"{escape_key(name)}={channel_value}")

        ts_epoch = _biosignal_timestamp(payload)
        line = (
            f"{INFLUX_EEG_TABLE},device={device},subject={subject},task={task},"
            f"recording_id={recording_id},source={source} "
            f"{','.join(fields)} {ts_epoch}"
        )
        _enqueue_line(line)
    except Exception as e:
        print(f"[Influx EEG] Error: {e}")


def write_ecg_to_influx(payload: dict) -> None:
    """
    Write clean ECG rows into the configured ECG measurement.
    """
    if not INFLUX_ENABLED:
        return

    try:
        device = escape_tag_value(payload.get("device", "ecg"))
        subject = escape_tag_value(payload.get("subject", "unknown"))
        task = escape_tag_value(payload.get("task", "unknown"))
        recording_id = escape_tag_value(payload.get("recording_id", "unknown"))
        source = escape_tag_value(payload.get("source", "openneuro_ds006848"))

        sample_idx = int(payload.get("sample_idx", 0))
        dataset_ts = _finite_float(payload.get("dataset_ts", payload.get("sensor_ts", 0.0)), "dataset_ts")
        sensor_ts = _finite_float(payload.get("sensor_ts", dataset_ts), "sensor_ts")
        sampling_rate_hz = _finite_float(payload.get("sampling_rate_hz", 0.0), "sampling_rate_hz")
        ecg_value = _finite_float(payload.get("ecg_value"), "ecg_value")
        quality = escape_field_string(payload.get("quality", "ok"))
        unit = escape_field_string(payload.get("unit", "V"))

        fields = [
            f"sample_idx={sample_idx}i",
            f"dataset_ts={dataset_ts}",
            f"sensor_ts={sensor_ts}",
            f"sampling_rate_hz={sampling_rate_hz}",
            f"ecg_value={ecg_value}",
            f'quality="{quality}"',
            f'unit="{unit}"',
        ]

        ts_epoch = _biosignal_timestamp(payload)
        line = (
            f"{INFLUX_ECG_TABLE},device={device},subject={subject},task={task},"
            f"recording_id={recording_id},source={source} "
            f"{','.join(fields)} {ts_epoch}"
        )
        _enqueue_line(line)
    except Exception as e:
        print(f"[Influx ECG] Error: {e}")
