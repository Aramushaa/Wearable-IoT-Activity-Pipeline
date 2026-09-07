"""HAR service entrypoint for database polling and live MQTT inference."""

from __future__ import annotations

import logging
import time

from .config import settings
from .inference_adapter import HarInferenceAdapter
from .influx import query_influx_sql
from .mqtt_stream import LiveHarMqttService
from .windowing import (
    build_sliding_windows,
    group_rows_by_device_and_recording,
    window_to_model_input,
)
from .writer import write_prediction_point

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

logger = logging.getLogger(__name__)

last_written_window_end_ts: dict[tuple[str, str], float] = {}


def sql_quote_literal(value: str) -> str:
    """Quote a SQL literal for the limited service-generated queries here."""
    return "'" + str(value).replace("'", "''") + "'"


def build_allowed_activity_clause() -> str | None:
    """Build an optional WHERE predicate for configured activity codes."""
    if not settings.allowed_activity_codes:
        return None

    allowed = ", ".join(
        sql_quote_literal(code)
        for code in settings.allowed_activity_codes
    )
    return f"activity_gt IN ({allowed})"


def fetch_matching_streams() -> list[dict]:
    """Find device/recording streams that currently have IMU data."""
    where_clauses = []

    if settings.filter_device:
        where_clauses.append(f"device = {sql_quote_literal(settings.filter_device)}")

    if settings.filter_recording_id:
        where_clauses.append(
            f"recording_id = {sql_quote_literal(settings.filter_recording_id)}"
        )

    allowed_activity_clause = build_allowed_activity_clause()
    if allowed_activity_clause:
        where_clauses.append(allowed_activity_clause)

    where_sql = ""
    if where_clauses:
        where_sql = "WHERE " + " AND ".join(where_clauses)

    sql = f"""
    SELECT
        device,
        recording_id,
        MAX(dataset_ts) AS max_dataset_ts
    FROM {settings.imu_table}
    {where_sql}
    GROUP BY device, recording_id
    ORDER BY device ASC, recording_id ASC
    """.strip()

    return query_influx_sql(sql)


def fetch_ordered_imu_rows(
    *,
    device: str,
    recording_id: str,
    limit: int,
) -> list[dict]:
    """Fetch rows for one stream in the order used to build HAR windows."""
    where_clauses = [
        f"device = {sql_quote_literal(device)}",
        f"recording_id = {sql_quote_literal(recording_id)}",
    ]

    allowed_activity_clause = build_allowed_activity_clause()
    if allowed_activity_clause:
        where_clauses.append(allowed_activity_clause)

    where_sql = "WHERE " + " AND ".join(where_clauses)
    limit_sql = f"LIMIT {limit}" if limit > 0 else ""

    sql = f"""
    SELECT
        time,
        device,
        recording_id,
        sample_idx,
        activity_gt,
        dataset_ts,
        acc_x,
        acc_y,
        acc_z,
        gyro_x,
        gyro_y,
        gyro_z
    FROM {settings.imu_table}
    {where_sql}
    ORDER BY time ASC, sample_idx ASC
    {limit_sql}
    """.strip()

    return query_influx_sql(sql)

def log_window_summary(
    device: str,
    recording_id: str,
    windows: list[list[dict]],
) -> None:
    """Log enough detail to verify window coverage without dumping samples."""
    if not windows:
        logger.info(
            "No complete windows | device=%s | recording_id=%s",
            device,
            recording_id,
        )
        return

    first_window = windows[0]
    first_row = first_window[0]
    last_row = first_window[-1]

    logger.info(
        "Built %s windows | device=%s | recording_id=%s | first_window_size=%s | first_dataset_ts=%s | last_dataset_ts=%s",
        len(windows),
        device,
        recording_id,
        len(first_window),
        first_row.get("dataset_ts"),
        last_row.get("dataset_ts"),
    )

def evaluate_windows_for_stream(
    device: str,
    recording_id: str,
    windows: list[list[dict]],
    inference,
    max_windows: int,
) -> None:
    """Run inference for new windows and persist prediction points."""
    if not windows:
        logger.info(
            "No windows to evaluate | device=%s | recording_id=%s",
            device,
            recording_id,
        )
        return

    predicted_counts: dict[str, int] = {}

    if max_windows > 0:
        windows_to_check = windows[:max_windows]
    else:
        windows_to_check = windows

    skipped_windows = max(0, len(windows) - len(windows_to_check))

    logger.info(
        "Window coverage | device=%s | recording_id=%s | total_windows=%s | checked_windows=%s | skipped_windows=%s | max_windows=%s",
        device,
        recording_id,
        len(windows),
        len(windows_to_check),
        skipped_windows,
        max_windows,
    )

    for idx, window in enumerate(windows_to_check):
        window_end_ts = float(window[-1]["dataset_ts"])

        # The polling loop may see the same rows repeatedly; this guard prevents
        # duplicate prediction points for a stream.
        if window_end_ts <= last_written_window_end_ts.get((device, recording_id), float("-inf")):
            logger.debug(
                "Skipping already written prediction | device=%s | recording_id=%s | window_idx=%s | end_dataset_ts=%s",
                device,
                recording_id,
                idx,
                window_end_ts,
            )
            continue

        model_input = window_to_model_input(window)
        prediction_details = inference.predict_details(model_input)
        prediction = prediction_details["predicted_label"]
        metadata = model_input["metadata"]

        predicted_counts[prediction] = predicted_counts.get(prediction, 0) + 1

        write_prediction_point(
            device=device,
            recording_id=recording_id,
            prediction=prediction,
            confidence=prediction_details["confidence"],
            metadata=metadata,
        )
        last_written_window_end_ts[(device, recording_id)] = window_end_ts

        logger.info(
            "Window prediction | device=%s | recording_id=%s | window_idx=%s | activity_gt=%s | predicted=%s | confidence=%.2f | top_k=%s | start_dataset_ts=%s | end_dataset_ts=%s",
            metadata["device"],
            metadata["recording_id"],
            idx,
            metadata["activity_gt"],
            prediction,
            prediction_details["confidence"],
            prediction_details["top_k"],
            metadata["start_dataset_ts"],
            metadata["end_dataset_ts"],
        )

    logger.info(
        "Prediction summary | device=%s | recording_id=%s | total_windows=%s | checked_windows=%s | skipped_windows=%s | predicted_counts=%s",
        device,
        recording_id,
        len(windows),
        len(windows_to_check),
        skipped_windows,
        predicted_counts,
    )


def main() -> None:
    """Initialize inference and run the configured HAR input mode."""
    logger.info("Starting %s", settings.service_name)
    logger.info(
        "Configuration | input_mode=%s | influx_database=%s | imu_table=%s | prediction_table=%s | query_limit=%s | window_size=%s | window_stride=%s | mqtt_topic=%s | prediction_topic=%s | model_path=%s | labels_path=%s",
        settings.input_mode,
        settings.influx_database,
        settings.imu_table,
        settings.prediction_table,
        settings.query_limit,
        settings.window_size,
        settings.window_stride,
        settings.mqtt_topic,
        settings.mqtt_prediction_topic,
        settings.model_path,
        settings.labels_path,
    )

    inference = HarInferenceAdapter(
        model_path=settings.model_path,
        labels_path=settings.labels_path,
        debug=settings.debug_inference,
        top_k=settings.prediction_top_k,
        input_layout=settings.input_layout,
        temporal_preprocess=settings.temporal_preprocess,
        score_aggregation=settings.score_aggregation,
    )
    logger.info("Inference engine initialized successfully")

    if settings.input_mode == "mqtt_stream":
        LiveHarMqttService(inference).run()
        return

    if settings.input_mode != "db_polling":
        raise ValueError(
            f"Unsupported HAR_INPUT_MODE={settings.input_mode!r}. "
            "Use 'db_polling' or 'mqtt_stream'."
        )

    try:
        while True:
            try:
                stream_summaries = fetch_matching_streams()
                logger.info("Found %s matching streams in %s", len(stream_summaries), settings.imu_table)

                if not stream_summaries:
                    logger.info("No matching streams found in %s", settings.imu_table)
                    time.sleep(settings.poll_interval_seconds)
                    continue

                total_windows = 0

                for summary in stream_summaries:
                    device = str(summary["device"])
                    recording_id = str(summary["recording_id"])
                    max_dataset_ts = float(summary["max_dataset_ts"])

                    if max_dataset_ts <= last_written_window_end_ts.get((device, recording_id), float("-inf")):
                        logger.debug(
                            "Skipping unchanged stream | device=%s | recording_id=%s | max_dataset_ts=%s",
                            device,
                            recording_id,
                            max_dataset_ts,
                        )
                        continue

                    group_rows = fetch_ordered_imu_rows(
                        device=device,
                        recording_id=recording_id,
                        limit=settings.query_limit,
                    )

                    if not group_rows:
                        logger.info(
                            "No rows fetched for matching stream | device=%s | recording_id=%s",
                            device,
                            recording_id,
                        )
                        continue

                    windows = build_sliding_windows(
                        rows=group_rows,
                        window_size=settings.window_size,
                        stride=settings.window_stride,
                    )

                    evaluate_windows_for_stream(
                        device=device,
                        recording_id=recording_id,
                        windows=windows,
                        inference=inference,
                        max_windows=settings.max_windows_per_stream,
                    )

                    total_windows += len(windows)
                    log_window_summary(device, recording_id, windows)

                logger.info("Total windows built in this cycle: %s", total_windows)

            except Exception:
                logger.exception("HAR cycle failed")

            time.sleep(settings.poll_interval_seconds)

    except KeyboardInterrupt:
        logger.warning("%s interrupted by user", settings.service_name)


if __name__ == "__main__":
    main()
