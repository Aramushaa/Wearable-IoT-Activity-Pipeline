"""Device discovery endpoint across configured sensor tables."""

from fastapi import APIRouter

from ..config import (
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_IMU_TABLE,
    INFLUX_WATCH_IMU_TABLE,
)
from ..influx import query_influx_sql

router = APIRouter(tags=["devices"])


def _safe_devices(table: str) -> list[str]:
    """Return distinct device values for a table, ignoring missing tables."""
    try:
        rows = query_influx_sql(
            f"SELECT DISTINCT device FROM {table} ORDER BY device ASC"
        )
        return [row["device"] for row in rows if "device" in row]
    except Exception:
        return []


@router.get("/devices")
def get_devices():
    """
    Return distinct device values from every configured sensor table.
    """
    tables = {
        "siddha_imu": INFLUX_IMU_TABLE,
        "watch_imu": INFLUX_WATCH_IMU_TABLE,
        "eeg": INFLUX_EEG_TABLE,
        "ecg": INFLUX_ECG_TABLE,
    }

    devices = []
    for source, table in tables.items():
        for device in _safe_devices(table):
            devices.append(
                {
                    "source": source,
                    "measurement": table,
                    "device": device,
                }
            )

    return {
        "count": len(devices),
        "devices": devices,
    }
