"""Structured sensor query endpoints backed by InfluxDB SQL."""

from typing import Optional

from fastapi import APIRouter, Query

from ..config import (
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_IMU_TABLE,
    INFLUX_WATCH_IMU_TABLE,
)
from ..influx import query_influx_sql
from ..utils.validators import validate_iso_timestamp, validate_sql_literal

router = APIRouter(prefix="/sensors", tags=["sensors"])


def _time_filters(from_ts: Optional[str], to_ts: Optional[str]) -> list[str]:
    """Build validated SQL predicates for optional time bounds."""
    where = []
    if from_ts:
        safe_from = validate_iso_timestamp(from_ts, "from")
        where.append(f"time >= '{safe_from}'")
    if to_ts:
        safe_to = validate_iso_timestamp(to_ts, "to")
        where.append(f"time <= '{safe_to}'")
    return where


def _common_filters(
    device: Optional[str],
    recording_id: Optional[str],
    from_ts: Optional[str],
    to_ts: Optional[str],
) -> list[str]:
    """Build common device/recording/time filters for sensor tables."""
    where = _time_filters(from_ts, to_ts)

    if device:
        safe_device = validate_sql_literal(device, "device")
        where.append(f"device = '{safe_device}'")

    if recording_id:
        safe_recording_id = validate_sql_literal(recording_id, "recording_id")
        where.append(f"recording_id = '{safe_recording_id}'")

    return where


def _where_sql(where: list[str]) -> str:
    """Render a WHERE clause only when at least one predicate exists."""
    return f"WHERE {' AND '.join(where)}" if where else ""


@router.get("/imu")
def get_dataset_imu(
    limit: int = Query(100, ge=1, le=5000),
    device: Optional[str] = Query(None),
    recording_id: Optional[str] = Query(None),
    activity_gt: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    order_by: str = Query("dataset_ts", pattern="^(dataset_ts|time)$"),
    order_dir: str = Query("asc", pattern="^(asc|desc)$"),
):
    """Query deterministic Siddha dataset IMU rows."""
    where = _common_filters(device, recording_id, from_ts, to_ts)

    if activity_gt:
        safe_activity_gt = validate_sql_literal(activity_gt, "activity_gt")
        where.append(f"activity_gt = '{safe_activity_gt}'")

    sql = f"""
    SELECT
        time,
        device,
        recording_id,
        sample_idx,
        activity_gt,
        dataset_ts,
        acc_x,
        acc_y,
        acc_z,
        gyro_x,
        gyro_y,
        gyro_z
    FROM {INFLUX_IMU_TABLE}
    {_where_sql(where)}
    ORDER BY {order_by} {order_dir.upper()}
    LIMIT {limit}
    """.strip()

    rows = query_influx_sql(sql)
    return {
        "measurement": INFLUX_IMU_TABLE,
        "count": len(rows),
        "rows": rows,
    }


@router.get("/watch")
def get_watch_imu(
    limit: int = Query(100, ge=1, le=5000),
    recording_id: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    order_by: str = Query("time", pattern="^(dataset_ts|time)$"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Query live MetaWear watch rows stored after cleaner normalization."""
    where = _common_filters("watch", recording_id, from_ts, to_ts)

    sql = f"""
    SELECT
        time,
        device,
        recording_id,
        sample_idx,
        dataset_ts,
        acc_x,
        acc_y,
        acc_z,
        gyro_x,
        gyro_y,
        gyro_z,
        activity_gt
    FROM {INFLUX_WATCH_IMU_TABLE}
    {_where_sql(where)}
    ORDER BY {order_by} {order_dir.upper()}
    LIMIT {limit}
    """.strip()

    rows = query_influx_sql(sql)
    return {
        "measurement": INFLUX_WATCH_IMU_TABLE,
        "count": len(rows),
        "rows": rows,
    }


@router.get("/eeg")
def get_eeg(
    limit: int = Query(100, ge=1, le=5000),
    subject: Optional[str] = Query(None),
    task: Optional[str] = Query(None),
    recording_id: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Query cleaned EEG rows and metadata from the biosignal table."""
    where = _time_filters(from_ts, to_ts)

    if subject:
        where.append(f"subject = '{validate_sql_literal(subject, 'subject')}'")
    if task:
        where.append(f"task = '{validate_sql_literal(task, 'task')}'")
    if recording_id:
        where.append(
            f"recording_id = '{validate_sql_literal(recording_id, 'recording_id')}'"
        )

    sql = f"""
    SELECT
        time,
        device,
        subject,
        task,
        recording_id,
        sample_idx,
        dataset_ts,
        sensor_ts,
        sampling_rate_hz,
        channel_count,
        quality
    FROM {INFLUX_EEG_TABLE}
    {_where_sql(where)}
    ORDER BY time {order_dir.upper()}
    LIMIT {limit}
    """.strip()

    rows = query_influx_sql(sql)
    return {
        "measurement": INFLUX_EEG_TABLE,
        "count": len(rows),
        "rows": rows,
    }


@router.get("/ecg")
def get_ecg(
    limit: int = Query(100, ge=1, le=5000),
    subject: Optional[str] = Query(None),
    task: Optional[str] = Query(None),
    recording_id: Optional[str] = Query(None),
    from_ts: Optional[str] = Query(None, alias="from"),
    to_ts: Optional[str] = Query(None, alias="to"),
    order_dir: str = Query("desc", pattern="^(asc|desc)$"),
):
    """Query cleaned ECG rows and metadata from the biosignal table."""
    where = _time_filters(from_ts, to_ts)

    if subject:
        where.append(f"subject = '{validate_sql_literal(subject, 'subject')}'")
    if task:
        where.append(f"task = '{validate_sql_literal(task, 'task')}'")
    if recording_id:
        where.append(
            f"recording_id = '{validate_sql_literal(recording_id, 'recording_id')}'"
        )

    sql = f"""
    SELECT
        time,
        device,
        subject,
        task,
        recording_id,
        sample_idx,
        dataset_ts,
        sensor_ts,
        sampling_rate_hz,
        ecg_value,
        unit,
        quality
    FROM {INFLUX_ECG_TABLE}
    {_where_sql(where)}
    ORDER BY time {order_dir.upper()}
    LIMIT {limit}
    """.strip()

    rows = query_influx_sql(sql)
    return {
        "measurement": INFLUX_ECG_TABLE,
        "count": len(rows),
        "rows": rows,
    }
