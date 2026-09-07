"""Reset the Phase 6 biosignal tables in InfluxDB 3.

This script is intentionally dependency-light so it can run from a local shell
without installing the service packages. It reads the project `.env`, validates
the configured table names, and deletes the EEG/ECG tables used by Phase 6
dataset replays.
"""

import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


ENV_PATH = Path(__file__).resolve().with_name(".env")
TABLE_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def load_env_file(path: Path = ENV_PATH) -> None:
    """Load simple KEY=VALUE pairs from `.env` without overriding the shell."""
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()

        if not key:
            continue

        if (value.startswith('"') and value.endswith('"')) or (
            value.startswith("'") and value.endswith("'")
        ):
            value = value[1:-1]
        else:
            value = value.split(" #", 1)[0].strip()

        value = re.sub(
            r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}",
            lambda match: os.environ.get(match.group(1), ""),
            value,
        )
        os.environ.setdefault(key, value)


def require_env(name: str) -> str:
    """Return a required environment value or fail with an actionable message."""
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is empty. Set it in .env or your terminal.")
    return value


def table_name_from_env(name: str, default: str) -> str:
    """Read and validate a table name before placing it in a request URL."""
    table_name = os.getenv(name, default).strip()
    if not TABLE_NAME_RE.fullmatch(table_name):
        raise RuntimeError(f"{name} has an invalid table name: {table_name!r}")
    return table_name


def host_for_local_run(host: str) -> str:
    """Map Docker service hostnames to localhost for direct local execution."""
    return host.replace("://influxdb3:", "://localhost:")


def delete_table(host: str, token: str, database: str, table: str) -> None:
    """Delete one InfluxDB table through the v3 configure API."""
    params = urlencode({"db": database, "table": table})
    url = f"{host}/api/v3/configure/table?{params}"

    req = Request(url, method="DELETE")
    req.add_header("Authorization", f"Bearer {token}")

    try:
        with urlopen(req, timeout=20) as resp:
            body = resp.read().decode("utf-8")
            if body:
                print(body)
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        if exc.code == 404:
            print(f"Table already absent: {table}")
            return
        raise RuntimeError(
            f"InfluxDB returned HTTP {exc.code} while deleting {table!r}: {body}"
        ) from exc
    except URLError as exc:
        raise RuntimeError(f"Could not reach InfluxDB at {host}: {exc.reason}") from exc


def main() -> None:
    """Load configuration and reset the configured Phase 6 tables."""
    load_env_file()

    influx_host = host_for_local_run(os.getenv("INFLUX_HOST", "http://localhost:8181"))
    influx_token = require_env("INFLUX_TOKEN")
    influx_database = os.getenv("INFLUX_DATABASE", "tennis").strip()
    tables = [
        table_name_from_env("INFLUX_EEG_TABLE", "eeg_clean"),
        table_name_from_env("INFLUX_ECG_TABLE", "ecg_clean"),
    ]

    for table in tables:
        print(f"Resetting table: {table}")
        delete_table(influx_host, influx_token, influx_database, table)

    print("Phase 6 EEG/ECG tables reset.")


if __name__ == "__main__":
    main()
