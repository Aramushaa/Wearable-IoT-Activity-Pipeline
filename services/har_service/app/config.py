"""Configuration for the HAR inference service."""

from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    """Runtime settings loaded from `HAR_*` environment variables."""

    service_name: str = "har-service"
    # Phase 3 uses db_polling for reproducible dataset evaluation.
    # Phase 4 uses mqtt_stream for live watch prediction.
    input_mode: str = "db_polling"
    poll_interval_seconds: float = 5.0

    # Opt-in: inferred dataset mapping, validated with a labeled watch trial.
    live_watch_preprocessing: bool = False

    mqtt_host: str = "emqx"
    mqtt_port: int = 1883
    mqtt_topic: str = "tennis/watch/clean"
    mqtt_prediction_topic: str = "tennis/watch/predictions"
    mqtt_qos: int = 1

    influx_host: str = "http://influxdb3:8181"
    influx_token: str = ""
    influx_database: str = "tennis"

    imu_table: str = "imu_raw_full_rows"
    prediction_table: str = "har_predictions_7_activity"

    model_path: str = "/app/model/L2MU_plain_leaky.onnx"
    labels_path: str = "/app/model/labels.txt"

    model_name: str = "L2MU_plain_leaky"
    input_layout: str = "accel_then_gyro"
    score_aggregation: str = "original"

    window_size: int = 40
    window_stride: int = 20
    live_window_stride: int = 1
    live_persistence_interval_seconds: float = 1.0
    max_windows_per_stream: int = 10
    query_limit: int = 5000
    prediction_top_k: int = 3
    debug_inference: bool = False
    temporal_preprocess: str = "none"

    filter_device: str | None = None
    filter_recording_id: str | None = None
    allowed_activity_gt: str = "F,G,O,P,Q,R,S"

    @property
    def allowed_activity_codes(self) -> list[str]:
        """Return configured Siddha activity codes as a clean list."""
        return [
            item.strip()
            for item in self.allowed_activity_gt.split(",")
            if item.strip()
        ]

    model_config = SettingsConfigDict(
        env_prefix="HAR_",
        env_file=".env",
        extra="ignore",
    )


settings = Settings()
