"""Input validators shared by FastAPI routers and configuration loading."""

import re
from datetime import datetime

from fastapi import HTTPException


_SAFE_SQL_LITERAL = re.compile(r"^[a-zA-Z0-9_\-]+$")
_SAFE_TABLE_NAME = re.compile(r"^[a-zA-Z0-9_\-]+$")


def validate_iso_timestamp(value: str, name: str) -> str:
    """
    Validate and normalize an ISO-8601 timestamp.
    """
    try:
        ts = value.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        return dt.isoformat()
    except (ValueError, TypeError):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid timestamp for '{name}': {value!r}. Expected ISO-8601 format.",
        )


def validate_sql_literal(value: str, name: str) -> str:
    """
    Validate a string that will be interpolated into SQL as a quoted literal.

    The routers interpolate these values into simple SQL strings, so we only
    allow letters, numbers, underscores, and hyphens.
    """
    if not _SAFE_SQL_LITERAL.fullmatch(value):
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid value for '{name}': {value!r}. "
                "Only letters, numbers, underscore, and hyphen are allowed."
            ),
        )
    return value


def validate_table_name(value: str, name: str) -> str:
    """
    Validate a config-defined SQL table/measurement name.
    """
    if not _SAFE_TABLE_NAME.fullmatch(value):
        raise ValueError(
            f"Invalid value for {name}: {value!r}. "
            "Only letters, numbers, underscore, and hyphen are allowed."
        )
    return value
