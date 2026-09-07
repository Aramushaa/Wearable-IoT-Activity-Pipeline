"""Time helpers shared by ingest modules."""

from datetime import datetime, timezone


def now_iso() -> str:
    """Return the current UTC timestamp as an ISO-8601 string."""
    return datetime.now(timezone.utc).isoformat()
