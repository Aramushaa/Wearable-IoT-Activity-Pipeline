"""Build and write HAR prediction points in Influx line protocol."""

from __future__ import annotations

from .config import settings
from .influx import escape_string_field, escape_tag_value, write_line_protocol

# Must match the base epoch used by the ingest service for dataset rows
# so that IMU data and prediction points share the same time axis.
DATASET_BASE_EPOCH_NS = 1704067200_000_000_000


def build_prediction_line(
    *,
    device: str,
    recording_id: str,
    prediction: str,
    confidence: float,
    metadata: dict,
) -> str:
    """Build the line-protocol row for one HAR prediction."""
    # MQTT live mode passes prediction_epoch_ns (wall-clock) so Grafana can
    # show predictions in real time.  DB-polling mode uses the synthetic base
    # epoch + dataset_ts for deterministic, reproducible alignment with the
    # dataset IMU rows stored by the ingest service.
    if "prediction_epoch_ns" in metadata:
        point_ts = int(metadata["prediction_epoch_ns"])
    else:
        point_ts = DATASET_BASE_EPOCH_NS + int(
            float(metadata["end_dataset_ts"]) * 1_000_000_000
        )

    return (
        f"{settings.prediction_table},"
        f"device={escape_tag_value(device)},"
        f"recording_id={escape_tag_value(recording_id)},"
        f"model_name={escape_tag_value(settings.model_name)},"
        f"input_layout={escape_tag_value(settings.input_layout)},"
        f"score_aggregation={escape_tag_value(settings.score_aggregation)} "
        f'predicted_label="{escape_string_field(prediction)}",'
        f'activity_gt="{escape_string_field(metadata["activity_gt"])}",'
        f"confidence={confidence},"
        f'window_start_dataset_ts={metadata["start_dataset_ts"]},'
        f'window_end_dataset_ts={metadata["end_dataset_ts"]},'
        f'window_size={metadata["window_size"]}i,'
        f'window_stride={settings.window_stride}i '
        f"{point_ts}"
    )


def write_prediction_point(
    *,
    device: str,
    recording_id: str,
    prediction: str,
    confidence: float,
    metadata: dict,
) -> None:
    """Write one HAR prediction point to InfluxDB."""
    write_line_protocol(
        build_prediction_line(
            device=device,
            recording_id=recording_id,
            prediction=prediction,
            confidence=confidence,
            metadata=metadata,
        )
    )
