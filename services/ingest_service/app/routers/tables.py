"""Expose configured InfluxDB table names to clients and dashboards."""

from fastapi import APIRouter

from ..config import (
    INFLUX_DATABASE,
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_IMU_TABLE,
    INFLUX_TABLE,
    INFLUX_WATCH_IMU_TABLE,
)

router = APIRouter(tags=["tables"])


@router.get("/tables")
def get_tables():
    """Return the database and measurement names currently in use."""
    return {
        "database": INFLUX_DATABASE,
        "tables": {
            "events": INFLUX_TABLE,
            "siddha_imu": INFLUX_IMU_TABLE,
            "watch_imu": INFLUX_WATCH_IMU_TABLE,
            "eeg": INFLUX_EEG_TABLE,
            "ecg": INFLUX_ECG_TABLE,
        },
    }
