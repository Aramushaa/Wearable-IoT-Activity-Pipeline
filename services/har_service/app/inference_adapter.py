"""Adapter between HAR service code and the bundled ONNX inference engine."""

from __future__ import annotations

import ast
from pathlib import Path

from model.inference_engine import InferenceEngine


def _clean_label(value: str) -> str:
    """Normalize one label token from the flexible labels file format."""
    return value.strip().strip(",").strip().strip("[](){}").strip("\"'")


def load_activity_labels(labels_path: str) -> list[str]:
    """Load labels from Python-list, comma-separated, or one-per-line formats."""
    path = Path(labels_path)
    if not path.exists():
        raise FileNotFoundError(f"Labels file not found: {labels_path}")

    raw_text = path.read_text(encoding="utf-8").strip()
    if not raw_text:
        raise ValueError(f"No labels found in: {labels_path}")

    candidate = raw_text
    if "=" in raw_text:
        _, rhs = raw_text.split("=", 1)
        candidate = rhs.strip()

    try:
        parsed = ast.literal_eval(candidate)
    except (SyntaxError, ValueError):
        parsed = None

    if isinstance(parsed, (list, tuple)):
        labels = [_clean_label(str(part)) for part in parsed if _clean_label(str(part))]
        if labels:
            return labels

    lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

    # Support either one-label-per-line or a single comma-separated line.
    if len(lines) == 1 and "," in lines[0]:
        labels = [_clean_label(part) for part in lines[0].split(",") if _clean_label(part)]
    else:
        labels = [_clean_label(line) for line in lines if _clean_label(line)]

    if not labels:
        raise ValueError(f"No labels found in: {labels_path}")

    return labels


class HarInferenceAdapter:
    """
    Thin wrapper around the provided InferenceEngine.

    Why this exists:
    - avoids modifying the professor assistant's file
    - captures callback output as a normal Python return value
    - keeps app-side integration clean
    """

    def __init__(
        self,
        model_path: str,
        labels_path: str,
        *,
        debug: bool = False,
        top_k: int = 3,
        input_layout: str = "accel_then_gyro",
        temporal_preprocess: str = "none",
        score_aggregation: str = "sum",
    ) -> None:
        self.last_prediction: str | None = None
        self.activity_labels = load_activity_labels(labels_path)
        self.engine = InferenceEngine(
            model_path,
            self.activity_labels,
            debug=debug,
            top_k=top_k,
            input_layout=input_layout,
            temporal_preprocess=temporal_preprocess,
            score_aggregation=score_aggregation,
        )
        self.engine.cb = self._capture_prediction
        self.engine.initialize()

    def _capture_prediction(self, activity: str) -> None:
        """Capture the callback emitted by the bundled inference engine."""
        self.last_prediction = activity

    def predict_details(self, model_input: dict) -> dict:
        """Run inference and verify callback output matches returned details."""
        self.last_prediction = None

        result = self.engine.execute_inference(
            accelerometer=model_input["accelerometer"],
            gyroscope=model_input["gyroscope"],
        )

        if self.last_prediction is None:
            raise RuntimeError("Inference completed but no prediction was captured from callback")

        if result["predicted_label"] != self.last_prediction:
            raise RuntimeError(
                "Inference callback prediction does not match returned result: "
                f"{self.last_prediction!r} != {result['predicted_label']!r}"
            )

        return result

    def predict(self, model_input: dict) -> str:
        """Return only the predicted activity label for callers that need it."""
        return self.predict_details(model_input)["predicted_label"]
