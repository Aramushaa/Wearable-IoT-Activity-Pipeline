"""Operational statistics endpoint for stored rows and writer health."""

from fastapi import APIRouter

from ..config import (
    INFLUX_ENABLED,
    INFLUX_ECG_TABLE,
    INFLUX_EEG_TABLE,
    INFLUX_IMU_TABLE,
    INFLUX_TABLE,
    INFLUX_WATCH_IMU_TABLE,
    INFLUX_WRITE_GENERIC_EVENTS,
)
from ..influx import query_influx_sql, get_influx_writer_stats

router = APIRouter(tags=["stats"])


def _safe_count(table: str) -> int:
    """Return the row count for *table*, or -1 if the table does not exist."""
    try:
        rows = query_influx_sql(f"SELECT COUNT(*) AS n FROM {table}")
        return rows[0]["n"] if rows else 0
    except Exception:
        return -1


def _safe_query(sql: str) -> list[dict] | None:
    """Run *sql* and return results, or None on failure."""
    try:
        return query_influx_sql(sql)
    except Exception:
        return None


@router.get("/stats")
def get_stats():
    """
    Return a compact operational summary of every data table and the
    writer queue.  Each query is wrapped so one missing or empty table
    does not crash the whole endpoint.
    """
    # Row counts are safe-counted because a fresh environment may not have
    # created every table yet.
    events_count = (
        _safe_count(INFLUX_TABLE) if INFLUX_WRITE_GENERIC_EVENTS else "disabled"
    )
    imu_count = _safe_count(INFLUX_IMU_TABLE)
    watch_imu_count = _safe_count(INFLUX_WATCH_IMU_TABLE)
    eeg_count = _safe_count(INFLUX_EEG_TABLE)
    ecg_count = _safe_count(INFLUX_ECG_TABLE)

    # Per-device breakdown for the deterministic dataset IMU table.
    devices = _safe_query(
        f"SELECT device, COUNT(*) AS n FROM {INFLUX_IMU_TABLE} "
        f"GROUP BY device ORDER BY n DESC"
    )

    # Writer internals expose queue pressure and retry/dropped-line counts.
    writer_stats = get_influx_writer_stats() if INFLUX_ENABLED else None

    return {
        "tables": {
            "events_full_rows": {
                "measurement": INFLUX_TABLE,
                "row_count": events_count,
            },
            "imu_raw_full_rows": {
                "measurement": INFLUX_IMU_TABLE,
                "row_count": imu_count,
            },
            "watch_imu_clean": {
                "measurement": INFLUX_WATCH_IMU_TABLE,
                "row_count": watch_imu_count,
            },
            "eeg_clean": {
                "measurement": INFLUX_EEG_TABLE,
                "row_count": eeg_count,
            },
            "ecg_clean": {
                "measurement": INFLUX_ECG_TABLE,
                "row_count": ecg_count,
            },
        },
        "devices": devices,
        "influx_writer": writer_stats,
    }
