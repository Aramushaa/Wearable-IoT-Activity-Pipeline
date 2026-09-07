"""
Comprehensive evaluation script for the HAR model.

This script:
  1. Queries InfluxDB for data across ALL 18 activity types
  2. Builds sliding windows and runs inference for each
  3. Prints a detailed report: ground truth -> predicted label, with confidence
  4. Produces a confusion-style summary

Run inside Docker:
    docker exec -it har-service python -m evaluate_model

Or locally (needs InfluxDB accessible at localhost:8181):
    HAR_INFLUX_HOST=http://localhost:8181 python evaluate_model.py
"""

from __future__ import annotations

import json
import os
import sys
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import numpy as np

from app.inference_adapter import load_activity_labels

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

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
LABELS_PATH = os.environ.get(
    "HAR_LABELS_PATH",
    str(Path(__file__).parent / "model" / "labels.txt"),
)

WINDOW_SIZE = int(os.environ.get("HAR_WINDOW_SIZE", "40"))
WINDOW_STRIDE = int(os.environ.get("HAR_WINDOW_STRIDE", "20"))
MAX_WINDOWS_PER_ACTIVITY = int(os.environ.get("HAR_MAX_WINDOWS_PER_ACTIVITY", "20"))
RECORDINGS_PER_ACTIVITY = int(os.environ.get("HAR_RECORDINGS_PER_ACTIVITY", "3"))
FETCH_LIMIT_PER_RECORDING = int(os.environ.get("HAR_FETCH_LIMIT_PER_RECORDING", "500"))
TOP_K_TO_PRINT = int(os.environ.get("HAR_TOP_K_TO_PRINT", "3"))
INPUT_LAYOUT = os.environ.get("HAR_INPUT_LAYOUT", "accel_then_gyro")
TEMPORAL_PREPROCESS = os.environ.get("HAR_TEMPORAL_PREPROCESS", "none")
SCORE_AGGREGATION = os.environ.get("HAR_SCORE_AGGREGATION", "sum")
FILTER_DEVICE = os.environ.get("HAR_FILTER_DEVICE")

# ---------------------------------------------------------------------------
# Full activity mapping from the Siddha dataset README
# ---------------------------------------------------------------------------

ACTIVITY_MAP = {
    "A": "Walking",
    "B": "Jogging",
    "C": "Stairs",
    "D": "Sitting",
    "E": "Standing",
    "M": "Kicking (Soccer)",
    "F": "Typing",
    "G": "Brushing Teeth",
    "O": "Playing Catch (Tennis)",
    "P": "Dribbling (Basketball)",
    "Q": "Writing",
    "R": "Clapping",
    "S": "Folding Clothes",
    "H": "Eating Soup",
    "I": "Eating Chips",
    "J": "Eating Pasta",
    "K": "Drinking from Cup",
    "L": "Eating Sandwich",
}

# Expected mapping from model label to Siddha dataset activity code.
EXPECTED_MAPPING = {
    "dribbling": "P",    # Dribbling (Basketball)
    "catch": "O",        # Playing Catch (Tennis)
    "typing": "F",       # Typing
    "writing": "Q",      # Writing
    "clapping": "R",     # Clapping
    "teeth": "G",        # Brushing Teeth
    "folding": "S",      # Folding Clothes
}


# ---------------------------------------------------------------------------
# InfluxDB query helper
# ---------------------------------------------------------------------------

def query_influx(sql: str) -> list[dict]:
    """Run one InfluxDB SQL query for the evaluation script."""
    if not INFLUX_TOKEN:
        print("ERROR: No InfluxDB token found. Set HAR_INFLUX_TOKEN or INFLUX_TOKEN env var.")
        sys.exit(1)

    params = urlencode({"db": INFLUX_DATABASE, "q": sql})
    url = f"{INFLUX_HOST}/api/v3/query_sql?{params}"

    req = Request(url, method="GET")
    req.add_header("Authorization", f"Bearer {INFLUX_TOKEN}")

    try:
        with urlopen(req, timeout=15) as resp:
            body = resp.read().decode("utf-8")
        return json.loads(body)
    except Exception as e:
        print(f"InfluxDB query failed: {e}")
        return []


# ---------------------------------------------------------------------------
# Windowing
# ---------------------------------------------------------------------------

def build_windows(rows: list[dict]) -> list[list[dict]]:
    """Build fixed-size windows with the configured stride."""
    windows = []
    if len(rows) < WINDOW_SIZE:
        return windows
    for start in range(0, len(rows) - WINDOW_SIZE + 1, WINDOW_STRIDE):
        windows.append(rows[start:start + WINDOW_SIZE])
    return windows


def window_to_arrays(window: list[dict]) -> tuple[dict, dict]:
    """Convert one IMU window into accelerometer and gyroscope axis arrays."""
    acc = {
        "x": [float(r["acc_x"]) for r in window],
        "y": [float(r["acc_y"]) for r in window],
        "z": [float(r["acc_z"]) for r in window],
    }
    gyro = {
        "x": [float(r["gyro_x"]) for r in window],
        "y": [float(r["gyro_y"]) for r in window],
        "z": [float(r["gyro_z"]) for r in window],
    }
    return acc, gyro


# ---------------------------------------------------------------------------
# Model inference (simplified, no callback needed)
# ---------------------------------------------------------------------------

def softmax(x, alpha=0.3):
    """Convert raw class scores to display probabilities."""
    x = np.asarray(x, dtype=np.float32)
    z = alpha * x
    z = z - np.max(z)
    exp_z = np.exp(z)
    return exp_z / np.sum(exp_z)


class SimpleInference:
    """Minimal inference wrapper for offline evaluation reports."""

    def __init__(self, model_path: str, labels: list[str]):
        from onnxruntime import InferenceSession, SessionOptions, ExecutionMode, GraphOptimizationLevel

        opts = SessionOptions()
        opts.execution_mode = ExecutionMode.ORT_SEQUENTIAL
        opts.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
        self.session = InferenceSession(model_path, sess_options=opts)
        self.labels = labels
        self.input_name = self.session.get_inputs()[0].name
        self.output_shape = self.session.get_outputs()[0].shape

    def _build_input_tensor(self, acc: dict, gyro: dict) -> np.ndarray:
        """Build the ONNX input tensor using the configured layout options."""
        accel = [acc["x"], acc["y"], acc["z"]]
        gyroscope = [gyro["x"], gyro["y"], gyro["z"]]

        if INPUT_LAYOUT == "accel_then_gyro":
            channels = accel + gyroscope
        elif INPUT_LAYOUT == "gyro_then_accel":
            channels = gyroscope + accel
        else:
            raise ValueError(
                f"Unsupported HAR_INPUT_LAYOUT={INPUT_LAYOUT!r}. "
                "Expected 'accel_then_gyro' or 'gyro_then_accel'."
            )

        data = np.array(channels, dtype=np.float32)

        if TEMPORAL_PREPROCESS == "none":
            processed = data
        elif TEMPORAL_PREPROCESS == "downsample2":
            processed = data[:, ::2]
        elif TEMPORAL_PREPROCESS == "meanpool2":
            if data.shape[1] % 2 != 0:
                raise ValueError(
                    "meanpool2 requires an even number of timesteps, "
                    f"got shape={data.shape}"
                )
            processed = data.reshape(data.shape[0], -1, 2).mean(axis=2)
        else:
            raise ValueError(
                f"Unsupported HAR_TEMPORAL_PREPROCESS={TEMPORAL_PREPROCESS!r}. "
                "Expected 'none', 'downsample2', or 'meanpool2'."
            )

        return np.expand_dims(processed.swapaxes(1, 0), 1).astype(np.float32)

    def _aggregate_scores(self, scores: np.ndarray) -> np.ndarray:
        """Reduce model output scores to one score per class."""
        if SCORE_AGGREGATION == "sum":
            if scores.ndim == 3:
                return np.sum(scores, axis=(0, 1))
            if scores.ndim == 2:
                return np.sum(scores, axis=0)
            if scores.ndim == 1:
                return scores
        elif SCORE_AGGREGATION == "last":
            if scores.ndim == 3:
                return scores[-1, 0, :]
            if scores.ndim == 2:
                return scores[-1, :]
            if scores.ndim == 1:
                return scores
        elif SCORE_AGGREGATION == "mean":
            if scores.ndim == 3:
                return np.mean(scores, axis=(0, 1))
            if scores.ndim == 2:
                return np.mean(scores, axis=0)
            if scores.ndim == 1:
                return scores

        raise ValueError(
            f"Unsupported HAR_SCORE_AGGREGATION={SCORE_AGGREGATION!r} "
            f"for output shape={scores.shape}"
        )

    def predict(self, acc: dict, gyro: dict) -> dict:
        """Run inference for one window and return prediction details."""
        model_input = self._build_input_tensor(acc, gyro)

        output = self.session.run(None, {self.input_name: model_input})
        scores = np.array(output[0])
        class_scores = self._aggregate_scores(scores)

        pred_idx = int(np.argmax(class_scores))
        probs = softmax(class_scores) * 100
        probs = np.round(probs, 2)

        top_k = min(TOP_K_TO_PRINT, len(self.labels))
        top_indices = np.argsort(class_scores)[::-1][:top_k]

        return {
            "predicted_label": self.labels[pred_idx],
            "predicted_idx": pred_idx,
            "confidence": float(probs[pred_idx]),
            "all_probs": {self.labels[i]: float(probs[i]) for i in range(len(self.labels))},
            "top_k": [(self.labels[i], float(probs[i])) for i in top_indices],
            "raw_scores": class_scores.tolist(),
            "output_shape": list(scores.shape),
        }


# ---------------------------------------------------------------------------
# Main evaluation
# ---------------------------------------------------------------------------

def get_distinct_activities() -> list[str]:
    """Find which activity codes actually exist in the database."""
    sql = f"SELECT DISTINCT activity_gt FROM {IMU_TABLE} ORDER BY activity_gt ASC"
    rows = query_influx(sql)
    activities = [r.get("activity_gt", r.get("distinct_activity_gt")) for r in rows if r]
    # Flatten in case of different response format
    flat = []
    for a in activities:
        if isinstance(a, str):
            flat.append(a)
    return flat


def get_recording_streams_for_activity(
    activity_code: str,
    limit: int = 3,
) -> list[tuple[str, str]]:
    """Get distinct (recording_id, device) streams for a given activity."""
    where = f"WHERE activity_gt = '{activity_code}'"
    if FILTER_DEVICE:
        where += f" AND device = '{FILTER_DEVICE}'"

    sql = f"""
    SELECT DISTINCT recording_id, device
    FROM {IMU_TABLE}
    {where}
    LIMIT {limit}
    """.strip()
    rows = query_influx(sql)
    streams: list[tuple[str, str]] = []
    for row in rows:
        if not row:
            continue
        recording_id = str(row.get("recording_id", row.get("distinct_recording_id", "")))
        device = str(row.get("device", ""))
        if recording_id and device:
            streams.append((recording_id, device))
    return streams


def fetch_activity_data(
    activity_code: str,
    recording_id: str | None = None,
    device: str | None = None,
    limit: int = 500,
) -> list[dict]:
    """Fetch IMU rows for a specific activity stream."""
    where = f"WHERE activity_gt = '{activity_code}'"
    if recording_id:
        where += f" AND recording_id = '{recording_id}'"
    if device:
        where += f" AND device = '{device}'"

    sql = f"""
    SELECT time, device, recording_id, sample_idx, activity_gt,
           dataset_ts, acc_x, acc_y, acc_z, gyro_x, gyro_y, gyro_z
    FROM {IMU_TABLE}
    {where}
    ORDER BY time ASC, sample_idx ASC
    LIMIT {limit}
    """.strip()
    return query_influx(sql)


def select_windows_round_robin(
    windows_by_stream: list[tuple[str | None, str | None, list[list[dict]]]],
    max_windows: int,
) -> list[tuple[str | None, str | None, int, list[dict], int, int]]:
    """
    Spread the evaluation budget across recordings instead of exhausting the first
    recording that has enough windows.

    Returns tuples:
      (recording_id, device, original_window_index, window, total_windows_for_stream, selected_count_for_stream)
    """
    selected: list[tuple[str | None, str | None, int, list[dict], int, int]] = []
    selected_counts: dict[tuple[str | None, str | None], int] = {
        (recording_id, device): 0 for recording_id, device, _ in windows_by_stream
    }

    next_idx = 0
    while len(selected) < max_windows:
        progress = False
        for recording_id, device, windows in windows_by_stream:
            if next_idx >= len(windows):
                continue

            stream_key = (recording_id, device)
            selected_counts[stream_key] += 1
            selected.append(
                (
                    recording_id,
                    device,
                    next_idx,
                    windows[next_idx],
                    len(windows),
                    selected_counts[stream_key],
                )
            )
            progress = True

            if len(selected) >= max_windows:
                break

        if not progress:
            break

        next_idx += 1

    return selected


def main():
    """Evaluate the model against activities currently stored in InfluxDB."""
    model_labels = load_activity_labels(LABELS_PATH)
    mapped_labels = {label: EXPECTED_MAPPING[label] for label in model_labels if label in EXPECTED_MAPPING}
    unmapped_labels = [label for label in model_labels if label not in EXPECTED_MAPPING]

    print("=" * 80)
    print("HAR MODEL COMPREHENSIVE EVALUATION")
    print("=" * 80)
    print(f"Model      : {MODEL_PATH}")
    print(f"Labels file : {LABELS_PATH}")
    print(f"Labels      : {model_labels}")
    print(f"InfluxDB   : {INFLUX_HOST}")
    print(f"Database   : {INFLUX_DATABASE}")
    print(f"Table      : {IMU_TABLE}")
    print(f"Window     : {WINDOW_SIZE} samples, stride {WINDOW_STRIDE}")
    print(f"Fetch limit: {FETCH_LIMIT_PER_RECORDING} rows / recording")
    print(f"Scope      : up to {RECORDINGS_PER_ACTIVITY} recording_ids and {MAX_WINDOWS_PER_ACTIVITY} windows / activity")
    print(f"Input mode : layout={INPUT_LAYOUT}, temporal={TEMPORAL_PREPROCESS}, aggregation={SCORE_AGGREGATION}")
    if FILTER_DEVICE:
        print(f"Device     : {FILTER_DEVICE}")
    print(f"Mapped labels to dataset codes: {mapped_labels}")
    if unmapped_labels:
        print(f"Unmapped labels: {unmapped_labels}")
    print()

    # Load model
    print("Loading ONNX model...")
    engine = SimpleInference(MODEL_PATH, model_labels)
    print("Model loaded successfully.\n")
    print(f"Model output shape metadata: {engine.output_shape}\n")

    # Discover activities in DB
    print("Discovering activities in database...")
    db_activities = get_distinct_activities()
    print(f"Found {len(db_activities)} activity codes: {db_activities}\n")

    # Results collector
    # gt_code -> list of predicted labels
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    activity_details: dict[str, list[dict]] = defaultdict(list)

    for code in db_activities:
        activity_name = ACTIVITY_MAP.get(code, f"UNKNOWN({code})")
        print("-" * 70)
        print(f"ACTIVITY: {code} = {activity_name}")
        print("-" * 70)

        # Get some recording IDs for variety
        streams = get_recording_streams_for_activity(code, limit=RECORDINGS_PER_ACTIVITY)
        if not streams:
            print(f"  No recording/device streams found for activity {code}. Trying without filter...")
            streams = [(None, None)]

        total_windows_available = 0
        windows_by_stream: list[tuple[str | None, str | None, list[list[dict]]]] = []
        for rec_id, device in streams:
            rows = fetch_activity_data(
                code,
                rec_id,
                device=device,
                limit=FETCH_LIMIT_PER_RECORDING,
            )
            if not rows:
                print(f"  No data for recording_id={rec_id} | device={device}")
                continue

            # Verify ground truth consistency in fetched rows
            gt_codes_in_data = set(r.get("activity_gt") for r in rows)
            devices_in_data = set(r.get("device") for r in rows)
            print(
                f"  recording_id={rec_id} | device={device} | rows={len(rows)} "
                f"| gt_codes_in_data={gt_codes_in_data} | devices_in_data={devices_in_data}"
            )

            windows = build_windows(rows)
            total_windows_available += len(windows)
            if not windows:
                print(f"    Not enough rows for a window (need {WINDOW_SIZE}, got {len(rows)})")
                continue

            print(
                f"    windows_available={len(windows)}"
            )
            windows_by_stream.append((rec_id, device, windows))

        selected_windows = select_windows_round_robin(
            windows_by_stream=windows_by_stream,
            max_windows=MAX_WINDOWS_PER_ACTIVITY,
        )
        total_windows_tested = len(selected_windows)
        streams_tested = len(windows_by_stream)

        selected_counts: dict[tuple[str | None, str | None], int] = defaultdict(int)
        for rec_id, device, _, _, _, _ in selected_windows:
            selected_counts[(rec_id, device)] += 1

        for rec_id, device, windows in windows_by_stream:
            count = selected_counts.get((rec_id, device), 0)
            skipped = len(windows) - count
            print(
                f"  recording_id={rec_id} | device={device} | windows_selected={count} | windows_skipped={skipped}"
            )

        for rec_id, device, source_w_idx, window, _, _ in selected_windows:
            acc, gyro = window_to_arrays(window)
            result = engine.predict(acc, gyro)

            pred = result["predicted_label"]
            conf = result["confidence"]
            top_k = result["top_k"]

            confusion[code][pred] += 1
            activity_details[code].append(result)

            expected_label = None
            for label, act_code in EXPECTED_MAPPING.items():
                if act_code == code:
                    expected_label = label
                    break

            correctness = ""
            if expected_label:
                correctness = " OK" if pred == expected_label else f" WRONG (expected: {expected_label})"

            print(
                f"    recording_id={rec_id} | device={device} | window[{source_w_idx:2d}] | pred={pred:12s} "
                f"| conf={conf:5.1f}% | top_k={top_k}{correctness}"
            )

        print(
            f"  Activity summary | streams_tested={streams_tested} "
            f"| windows_available={total_windows_available} | windows_tested={total_windows_tested}\n"
        )

    # ---------------------------------------------------------------------------
    # SUMMARY REPORT
    # ---------------------------------------------------------------------------
    print("\n" + "=" * 80)
    print("SUMMARY: Ground Truth -> Prediction Distribution")
    print("=" * 80)
    print(f"{'GT Code':<8} {'Activity Name':<25} {'In Model?':<10} {'Predictions'}")
    print("-" * 80)

    for code in sorted(confusion.keys()):
        name = ACTIVITY_MAP.get(code, "UNKNOWN")
        in_model = any(v == code for v in EXPECTED_MAPPING.values())
        preds = dict(confusion[code])
        total = sum(preds.values())

        # Format prediction distribution
        pred_str_parts = []
        for label, count in sorted(preds.items(), key=lambda x: -x[1]):
            pct = count / total * 100
            pred_str_parts.append(f"{label}={count}({pct:.0f}%)")
        pred_str = ", ".join(pred_str_parts)

        print(f"{code:<8} {name:<25} {'YES' if in_model else 'NO':<10} {pred_str}")

    print("-" * 80)

    # Accuracy for the 7 activities that ARE in the model
    print("\nACCURACY for model's 7 activities:")
    print("-" * 50)
    correct_total = 0
    tested_total = 0
    for label, act_code in sorted(EXPECTED_MAPPING.items(), key=lambda x: x[1]):
        if act_code not in confusion:
            print(f"  {act_code} ({label}): NO DATA")
            continue
        preds = confusion[act_code]
        total = sum(preds.values())
        correct = preds.get(label, 0)
        acc = correct / total * 100 if total > 0 else 0
        correct_total += correct
        tested_total += total
        print(f"  {act_code} ({label:12s}): {correct}/{total} correct = {acc:.1f}%")

    if tested_total > 0:
        overall = correct_total / tested_total * 100
        print(f"\n  OVERALL: {correct_total}/{tested_total} = {overall:.1f}%")

    print("\n" + "=" * 80)
    print("EVALUATION COMPLETE")
    print("=" * 80)


if __name__ == "__main__":
    main()
