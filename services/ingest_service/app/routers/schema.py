"""Schema inspection endpoints for configured InfluxDB tables."""

from fastapi import APIRouter

from ..config import (
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_IMU_TABLE,
    INFLUX_TABLE,
    INFLUX_WATCH_IMU_TABLE,
)
from ..influx import query_influx_sql

router = APIRouter(tags=["schema"])


def _safe_query(sql: str) -> list[dict] | None:
    """Return None instead of failing the whole schema response."""
    try:
        return query_influx_sql(sql)
    except Exception:
        return None


@router.get("/schema")
def get_schema():
    """
    Return schema information for the configured InfluxDB tables.
    """
    events_sql = f"SHOW COLUMNS FROM {INFLUX_TABLE}"
    imu_sql = f"SHOW COLUMNS FROM {INFLUX_IMU_TABLE}"
    watch_imu_sql = f"SHOW COLUMNS FROM {INFLUX_WATCH_IMU_TABLE}"
    eeg_sql = f"SHOW COLUMNS FROM {INFLUX_EEG_TABLE}"
    ecg_sql = f"SHOW COLUMNS FROM {INFLUX_ECG_TABLE}"

    events_schema = _safe_query(events_sql)
    imu_schema = _safe_query(imu_sql)
    watch_imu_schema = _safe_query(watch_imu_sql)
    eeg_schema = _safe_query(eeg_sql)
    ecg_schema = _safe_query(ecg_sql)

    return {
        "events_measurement": INFLUX_TABLE,
        "events_schema": events_schema,
        "imu_measurement": INFLUX_IMU_TABLE,
        "imu_schema": imu_schema,
        "watch_imu_measurement": INFLUX_WATCH_IMU_TABLE,
        "watch_imu_schema": watch_imu_schema,
        "eeg_measurement": INFLUX_EEG_TABLE,
        "eeg_schema": eeg_schema,
        "ecg_measurement": INFLUX_ECG_TABLE,
        "ecg_schema": ecg_schema,
    }


@router.get("/events/schema")
def get_events_schema_legacy():
    """Compatibility alias for older clients that queried `/events/schema`."""
    return get_schema()
