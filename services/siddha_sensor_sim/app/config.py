"""Configuration for the Siddha IMU dataset replay service."""

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings loaded from `SIDDHA_*` environment variables."""

    mqtt_broker_host: str = "emqx"
    mqtt_broker_port: int = 1883
    mqtt_topic_prefix: str = "tennis/sensor"
    mqtt_qos: int = 0
    mqtt_wait_for_publish: bool = False

    dataset_path: str = "/app/dataset/data.parquet"

    replay_mode: str = "realtime"   # "realtime" preserves dataset timing; "fast" skips sleeps.
    replay_speed: float = 1.0       # 1.0 = real time, 2.0 = twice as fast.
    loop_forever: bool = False
    
    default_device_filter: str | None = None
    default_activity_filter: str | None = None
    default_recording_id_filter: str | None = None
    

    @model_validator(mode="before")
    @classmethod
    def empty_strings_to_none(cls, values):
        """Convert empty-string env vars to None so filters are skipped."""
        filter_fields = [
            "default_device_filter",
            "default_activity_filter",
            "default_recording_id_filter",
        ]
        for field in filter_fields:
            if field in values and values[field] == "":
                values[field] = None
        return values

    model_config = SettingsConfigDict(
        env_prefix="SIDDHA_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
