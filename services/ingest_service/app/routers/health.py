"""Health endpoint for container orchestration and manual diagnostics."""

from fastapi import APIRouter

from ..config import INFLUX_ENABLED
from ..influx import get_influx_writer_stats

router = APIRouter(tags=["health"])


@router.get("/health")
def health():
    """Return service liveness plus writer state when InfluxDB is enabled."""
    writer_stats = get_influx_writer_stats() if INFLUX_ENABLED else None

    return {
        "status": "ok",
        "service": "ingest-service",
        "influx_enabled": INFLUX_ENABLED,
        "influx_writer": writer_stats,
    }
