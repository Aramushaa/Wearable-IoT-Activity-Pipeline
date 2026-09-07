"""
Preprocessing sweep for the bundled HAR model.

Purpose:
- evaluate the ONNX model on device-separated streams
- compare channel order, per-channel preprocessing, and temporal reduction
- identify which runtime assumptions make the supplied model behave best

Run inside Docker, for example:
    docker exec \
      -e HAR_FIX_DEVICE_FILTER=watch \
      -e HAR_FIX_RECORDINGS_PER_ACTIVITY=5 \
      -e HAR_FIX_WINDOWS_PER_STREAM=3 \
      har-service python /app/fix_finder.py
"""

from __future__ import annotations

import json
import os
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np
from onnxruntime import ExecutionMode, GraphOptimizationLevel, InferenceSession, SessionOptions

INFLUX_HOST = os.environ.get("HAR_INFLUX_HOST", "http://localhost:8181")
INFLUX_TOKEN = os.environ.get(
    "HAR_INFLUX_TOKEN",
    os.environ.get("INFLUX_TOKEN", ""),
)
INFLUX_DATABASE = os.environ.get("HAR_INFLUX_DATABASE", "tennis")
IMU_TABLE = os.environ.get("HAR_IMU_TABLE", "imu_raw_full_rows")
MODEL_PATH = os.environ.get(
    "HAR_MODEL_PATH",
    str(Path(__file__).parent / "model" / "L2MU_plain_leaky.onnx"),
)

WINDOW_SIZE = int(os.environ.get("HAR_FIX_WINDOW_SIZE", "40"))
WINDOW_STRIDE = int(os.environ.get("HAR_FIX_WINDOW_STRIDE", "20"))
RECORDINGS_PER_ACTIVITY = int(os.environ.get("HAR_FIX_RECORDINGS_PER_ACTIVITY", "5"))
FETCH_LIMIT_PER_STREAM = int(os.environ.get("HAR_FIX_FETCH_LIMIT_PER_STREAM", "1500"))
WINDOWS_PER_STREAM = int(os.environ.get("HAR_FIX_WINDOWS_PER_STREAM", "3"))
DEVICE_FILTER = os.environ.get("HAR_FIX_DEVICE_FILTER")
MIN_REPORT_ACCURACY = float(os.environ.get("HAR_FIX_MIN_REPORT_ACCURACY", "25"))

EXPECTED = {
    "dribbling": "P",
    "catch": "O",
    "typing": "F",
    "writing": "Q",
    "clapping": "R",
    "teeth": "G",
    "folding": "S",
}
MODEL_LABELS = ["dribbling", "catch", "typing", "writing", "clapping", "teeth", "folding"]


def query(sql: str) -> list[dict]:
    """Run one InfluxDB SQL query for the preprocessing sweep."""
    params = urlencode({"db": INFLUX_DATABASE, "q": sql})
    url = f"{INFLUX_HOST}/api/v3/query_sql?{params}"
    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")
    with urlopen(req, timeout=15) as resp:
        return json.loads(resp.read().decode())


def fetch_streams(activity_code: str, limit: int) -> list[tuple[str, str]]:
    """Fetch device-separated streams for one dataset activity code."""
    where = f"WHERE activity_gt = '{activity_code}'"
    if DEVICE_FILTER:
        where += f" AND device = '{DEVICE_FILTER}'"

    sql = f"""
    SELECT DISTINCT recording_id, device
    FROM {IMU_TABLE}
    {where}
    LIMIT {limit}
    """.strip()

    rows = query(sql)
    streams: list[tuple[str, str]] = []
    for row in rows:
        recording_id = str(row.get("recording_id", ""))
        device = str(row.get("device", ""))
        if recording_id and device:
            streams.append((recording_id, device))
    return streams


def fetch_rows(activity_code: str, recording_id: str, device: str, limit: int) -> list[dict]:
    """Fetch raw IMU columns for one activity/device/recording stream."""
    sql = f"""
    SELECT acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
    FROM {IMU_TABLE}
    WHERE activity_gt = '{activity_code}'
      AND recording_id = '{recording_id}'
      AND device = '{device}'
    ORDER BY time ASC, sample_idx ASC
    LIMIT {limit}
    """.strip()
    return query(sql)


def make_windows(rows: list[dict], max_windows: int) -> list[list[dict]]:
    """Build a limited set of sliding windows from ordered rows."""
    windows = [
        rows[idx:idx + WINDOW_SIZE]
        for idx in range(0, len(rows) - WINDOW_SIZE + 1, WINDOW_STRIDE)
    ]
    return windows[:max_windows]


def rows_to_channels(window: list[dict], layout: str) -> np.ndarray:
    """Convert a window into channel-first accelerometer/gyroscope data."""
    accel = np.array(
        [
            [float(row["acc_x"]) for row in window],
            [float(row["acc_y"]) for row in window],
            [float(row["acc_z"]) for row in window],
        ],
        dtype=np.float32,
    )
    gyro = np.array(
        [
            [float(row["gyro_x"]) for row in window],
            [float(row["gyro_y"]) for row in window],
            [float(row["gyro_z"]) for row in window],
        ],
        dtype=np.float32,
    )

    if layout == "accel_then_gyro":
        return np.vstack([accel, gyro])
    if layout == "gyro_then_accel":
        return np.vstack([gyro, accel])
    raise ValueError(f"Unsupported layout: {layout}")


def apply_channel_preprocess(data: np.ndarray, mode: str) -> np.ndarray:
    """Apply one channel-normalization candidate to a window."""
    processed = data.copy()

    if mode == "none":
        return processed

    if mode == "demean_all":
        means = processed.mean(axis=1, keepdims=True)
        return processed - means

    if mode == "demean_accel":
        processed[:3] = processed[:3] - processed[:3].mean(axis=1, keepdims=True)
        return processed

    if mode == "zscore_all":
        means = processed.mean(axis=1, keepdims=True)
        stds = processed.std(axis=1, keepdims=True)
        stds = np.where(stds > 1e-8, stds, 1.0)
        return (processed - means) / stds

    if mode == "zscore_accel":
        means = processed[:3].mean(axis=1, keepdims=True)
        stds = processed[:3].std(axis=1, keepdims=True)
        stds = np.where(stds > 1e-8, stds, 1.0)
        processed[:3] = (processed[:3] - means) / stds
        return processed

    raise ValueError(f"Unsupported preprocess mode: {mode}")


def apply_temporal_preprocess(data: np.ndarray, mode: str) -> np.ndarray:
    """Apply one temporal-reduction candidate to a window."""
    if mode == "none":
        return data

    if mode == "downsample2":
        return data[:, ::2]

    if mode == "meanpool2":
        if data.shape[1] % 2 != 0:
            raise ValueError(f"meanpool2 requires even timesteps, got {data.shape}")
        return data.reshape(data.shape[0], -1, 2).mean(axis=2)

    raise ValueError(f"Unsupported temporal preprocess: {mode}")


def build_input_tensor(window: list[dict], layout: str, preprocess: str, temporal: str) -> np.ndarray:
    """Build one ONNX input tensor for a sweep configuration."""
    data = rows_to_channels(window, layout=layout)
    data = apply_channel_preprocess(data, mode=preprocess)
    data = apply_temporal_preprocess(data, mode=temporal)
    return np.expand_dims(data.swapaxes(1, 0), 1).astype(np.float32)


def aggregate_scores(output: list[np.ndarray], mode: str) -> np.ndarray:
    """Reduce ONNX output scores to one score per model label."""
    scores = np.array(output[0])

    if mode == "sum":
        if scores.ndim == 3:
            return np.sum(scores, axis=(0, 1))
        if scores.ndim == 2:
            return np.sum(scores, axis=0)
        return scores

    if mode == "last":
        if scores.ndim == 3:
            return scores[-1, 0, :]
        if scores.ndim == 2:
            return scores[-1, :]
        return scores

    if mode == "mean":
        if scores.ndim == 3:
            return np.mean(scores, axis=(0, 1))
        if scores.ndim == 2:
            return np.mean(scores, axis=0)
        return scores

    if mode == "mid":
        if scores.ndim == 3:
            mid = scores.shape[0] // 2
            return scores[mid, 0, :]
        if scores.ndim == 2:
            mid = scores.shape[0] // 2
            return scores[mid, :]
        return scores

    raise ValueError(f"Unsupported aggregation mode: {mode}")


def collect_windows() -> dict[str, list[list[dict]]]:
    """Collect a balanced pool of windows for each expected activity."""
    windows_by_activity: dict[str, list[list[dict]]] = defaultdict(list)

    print("-" * 70, flush=True)
    print("Collecting device-separated windows", flush=True)
    print("-" * 70, flush=True)

    for label, code in EXPECTED.items():
        streams = fetch_streams(code, limit=RECORDINGS_PER_ACTIVITY)
        if not streams:
            print(f"  {code}({label}): no streams found", flush=True)
            continue

        print(f"  {code}({label}): {len(streams)} streams", flush=True)
        for recording_id, device in streams:
            rows = fetch_rows(code, recording_id, device, limit=FETCH_LIMIT_PER_STREAM)
            windows = make_windows(rows, max_windows=WINDOWS_PER_STREAM)
            windows_by_activity[code].extend(windows)
            print(
                f"    recording_id={recording_id} | device={device} | rows={len(rows)} | windows={len(windows)}",
                flush=True,
            )

    return dict(windows_by_activity)


def evaluate_config(
    session: InferenceSession,
    input_name: str,
    windows_by_activity: dict[str, list[list[dict]]],
    *,
    layout: str,
    preprocess: str,
    temporal: str,
    aggregation: str,
) -> tuple[int, int, dict[str, tuple[int, int]]]:
    """Evaluate one layout/preprocess/temporal/aggregation configuration."""
    correct = 0
    total = 0
    per_label: dict[str, tuple[int, int]] = {}

    for label, code in EXPECTED.items():
        wins = windows_by_activity.get(code, [])
        label_correct = 0
        label_total = 0

        for window in wins:
            model_input = build_input_tensor(
                window,
                layout=layout,
                preprocess=preprocess,
                temporal=temporal,
            )
            output = session.run(None, {input_name: model_input})
            class_scores = aggregate_scores(output, mode=aggregation)
            prediction = MODEL_LABELS[int(np.argmax(class_scores))]

            if prediction == label:
                correct += 1
                label_correct += 1

            total += 1
            label_total += 1

        per_label[label] = (label_correct, label_total)

    return correct, total, per_label


def is_model_input_compatible(
    session: InferenceSession,
    input_name: str,
    sample_window: list[dict],
    *,
    layout: str,
    preprocess: str,
    temporal: str,
) -> tuple[bool, str | None]:
    """Check whether a configuration produces a tensor accepted by the model."""
    try:
        model_input = build_input_tensor(
            sample_window,
            layout=layout,
            preprocess=preprocess,
            temporal=temporal,
        )
        session.run(None, {input_name: model_input})
        return True, None
    except Exception as exc:
        return False, str(exc)


def format_label_summary(per_label: dict[str, tuple[int, int]]) -> str:
    """Format per-label accuracy compactly for console output."""
    parts = []
    for label in ("typing", "teeth", "catch", "dribbling", "writing", "clapping", "folding"):
        correct, total = per_label.get(label, (0, 0))
        pct = (correct / total * 100) if total else 0.0
        parts.append(f"{label}={correct}/{total}({pct:.0f}%)")
    return ", ".join(parts)


def main() -> None:
    """Run the preprocessing sweep and print the best configurations."""
    print("=" * 70, flush=True)
    print("HAR PREPROCESSING SWEEP", flush=True)
    print("=" * 70, flush=True)
    print(f"Device filter          : {DEVICE_FILTER or 'all'}", flush=True)
    print(f"Recordings / activity  : {RECORDINGS_PER_ACTIVITY}", flush=True)
    print(f"Windows / stream       : {WINDOWS_PER_STREAM}", flush=True)
    print(f"Fetch limit / stream   : {FETCH_LIMIT_PER_STREAM}", flush=True)
    print(f"Window size / stride   : {WINDOW_SIZE} / {WINDOW_STRIDE}", flush=True)

    options = SessionOptions()
    options.execution_mode = ExecutionMode.ORT_SEQUENTIAL
    options.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
    session = InferenceSession(MODEL_PATH, sess_options=options)
    input_name = session.get_inputs()[0].name

    windows_by_activity = collect_windows()
    total_windows = sum(len(wins) for wins in windows_by_activity.values())
    if total_windows == 0:
        print("No windows collected. Nothing to evaluate.", flush=True)
        return

    print(f"\nCollected windows: {total_windows}", flush=True)
    print(f"Model input name : {input_name}", flush=True)
    print(f"Output shape meta: {session.get_outputs()[0].shape}", flush=True)
    sample_window = next(iter(next(iter(windows_by_activity.values()))))

    layouts = ["accel_then_gyro", "gyro_then_accel"]
    preprocesses = ["none", "demean_all", "demean_accel", "zscore_all", "zscore_accel"]
    temporals = ["none", "downsample2", "meanpool2"]
    aggregations = ["sum", "last", "mean", "mid"]

    results: list[dict] = []

    print("\n" + "-" * 70, flush=True)
    print("Running sweep", flush=True)
    print("-" * 70, flush=True)

    for layout in layouts:
        for preprocess in preprocesses:
            for temporal in temporals:
                for aggregation in aggregations:
                    compatible, error = is_model_input_compatible(
                        session,
                        input_name,
                        sample_window,
                        layout=layout,
                        preprocess=preprocess,
                        temporal=temporal,
                    )
                    if not compatible:
                        if aggregation == aggregations[0]:
                            print(
                                f"  skip | layout={layout:15s} | preprocess={preprocess:12s} "
                                f"| temporal={temporal:9s} | reason=input mismatch",
                                flush=True,
                            )
                        continue

                    correct, total, per_label = evaluate_config(
                        session,
                        input_name,
                        windows_by_activity,
                        layout=layout,
                        preprocess=preprocess,
                        temporal=temporal,
                        aggregation=aggregation,
                    )
                    accuracy = (correct / total * 100) if total else 0.0
                    result = {
                        "layout": layout,
                        "preprocess": preprocess,
                        "temporal": temporal,
                        "aggregation": aggregation,
                        "correct": correct,
                        "total": total,
                        "accuracy": accuracy,
                        "per_label": per_label,
                    }
                    results.append(result)

                    if accuracy >= MIN_REPORT_ACCURACY:
                        print(
                            f"  {accuracy:5.1f}% | layout={layout:15s} | preprocess={preprocess:12s} "
                            f"| temporal={temporal:9s} | aggregation={aggregation:4s}",
                            flush=True,
                        )
                        print(
                            f"           {format_label_summary(per_label)}",
                            flush=True,
                        )

    results.sort(key=lambda item: item["accuracy"], reverse=True)

    print("\n" + "=" * 70, flush=True)
    print("Top 10 configurations", flush=True)
    print("=" * 70, flush=True)
    for idx, result in enumerate(results[:10], start=1):
        print(
            f"{idx:2d}. {result['accuracy']:5.1f}% | layout={result['layout']} | "
            f"preprocess={result['preprocess']} | temporal={result['temporal']} | "
            f"aggregation={result['aggregation']} | {result['correct']}/{result['total']}",
            flush=True,
        )
        print(f"    {format_label_summary(result['per_label'])}", flush=True)


if __name__ == "__main__":
    main()
