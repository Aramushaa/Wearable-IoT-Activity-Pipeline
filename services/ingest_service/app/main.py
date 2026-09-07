"""FastAPI entrypoint for MQTT ingest, query, and health endpoints."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .config import INFLUX_ENABLED
from .influx import start_influx_writer, stop_influx_writer
from .mqtt import start_mqtt_thread, stop_mqtt
from .routers.health import router as health_router
from .routers.events import router as events_router
from .routers.imu import router as imu_router
from .routers.devices import router as devices_router
from .routers.stats import router as stats_router
from .routers.schema import router as schema_router
from .routers.tables import router as tables_router
from .routers.sensors import router as sensors_router



@asynccontextmanager
async def lifespan(app: FastAPI):
    """Start and stop background workers with the FastAPI application."""
    if INFLUX_ENABLED:
        start_influx_writer()
    start_mqtt_thread()
    print("[APP] startup complete")

    yield

    stop_mqtt()
    if INFLUX_ENABLED:
        stop_influx_writer()
    print("[APP] shutdown complete")


app = FastAPI(title="ingest-service", version="0.4.0", lifespan=lifespan)

# Routers are kept small by topic: diagnostics, raw events, structured sensor
# queries, and operational metadata.
app.include_router(health_router)
app.include_router(events_router)
app.include_router(imu_router)
app.include_router(devices_router)
app.include_router(stats_router)
app.include_router(schema_router)
app.include_router(tables_router)
app.include_router(sensors_router)
