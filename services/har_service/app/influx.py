"""InfluxDB helpers used by the HAR service."""

from __future__ import annotations

import json
import logging
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from .config import settings

logger = logging.getLogger(__name__)


def escape_tag_value(value: str) -> str:
    """Escape an InfluxDB line-protocol tag value."""
    return str(value).replace(" ", "\\ ").replace(",", "\\,").replace("=", "\\=")


def escape_string_field(value: str) -> str:
    """Escape an InfluxDB line-protocol string field."""
    return str(value).replace("\\", "\\\\").replace('"', '\\"')


def write_line_protocol(line: str) -> None:
    """Write one line-protocol point to the configured InfluxDB database."""
    params = urlencode({"db": settings.influx_database, "precision": "ns"})
    url = f"{settings.influx_host}/api/v3/write_lp?{params}"

    req = Request(
        url,
        data=line.encode("utf-8"),
        method="POST",
        headers={
            "Authorization": f"Bearer {settings.influx_token}",
            "Content-Type": "text/plain; charset=utf-8",
        },
    )

    with urlopen(req, timeout=10) as resp:
        body = resp.read()
        logger.debug(
            "[INFLUX WRITE] status=%s db=%s line=%s",
            resp.status,
            settings.influx_database,
            line,
        )
        if body:
            logger.debug(
                "[INFLUX WRITE BODY] %s",
                body.decode("utf-8", errors="replace"),
            )


def query_influx_sql(sql: str) -> list[dict]:
    """Run a SQL query against InfluxDB 3 and return decoded rows."""
    if not settings.influx_token:
        raise RuntimeError("HAR_INFLUX_TOKEN is empty")

    params = urlencode({
        "db": settings.influx_database,
        "q": sql,
    })
    url = f"{settings.influx_host}/api/v3/query_sql?{params}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {settings.influx_token}")

    with urlopen(req, timeout=10) as resp:
        body = resp.read().decode("utf-8")

    return json.loads(body)
