"""ONNX inference engine for the bundled 7-activity HAR model."""

import numpy as np
from onnxruntime import SessionOptions, InferenceSession, ExecutionMode, GraphOptimizationLevel
from typing import Callable, List


def softmax(x, alpha=0.3):
    """Convert model scores to display probabilities with temperature scaling."""
    x = np.asarray(x, dtype=np.float32)
    z = alpha * x
    z = z - np.max(z)
    exp_z = np.exp(z)
    return exp_z / np.sum(exp_z)


class InferenceEngine:
    """Prepare model tensors, run ONNX Runtime, and format predictions."""

    def __init__(
        self,
        model_path,
        activity_labels,
        *,
        debug: bool = False,
        top_k: int = 3,
        input_layout: str = "accel_then_gyro",
        temporal_preprocess: str = "none",
        score_aggregation: str = "sum",
    ):
        self.session = None
        self.model_path = model_path
        self.activity_labels: List = [str(label) for label in activity_labels]
        if not self.activity_labels:
            raise ValueError("activity_labels cannot be empty")

        self.cb: Callable = self.default_callback
        self.debug = debug
        self.top_k = max(1, int(top_k))
        self.last_result: dict | None = None
        self.input_layout = input_layout
        self.temporal_preprocess = temporal_preprocess
        self.score_aggregation = score_aggregation

    def _debug_print(self, *parts) -> None:
        """Print debug output only when debug mode is enabled."""
        if self.debug:
            print(*parts)

    def _resolve_output_classes(self) -> int | None:
        """Infer the number of model classes from output metadata if possible."""
        if self.session is None:
            raise RuntimeError("Inference session is not initialized")

        output_meta = self.session.get_outputs()[0]
        for dim in reversed(output_meta.shape):
            if isinstance(dim, int) and dim > 0:
                return dim
        return None

    def _resolve_expected_input_shape(self) -> list[int | str | None]:
        """Read the ONNX input shape used for runtime validation."""
        if self.session is None:
            raise RuntimeError("Inference session is not initialized")

        return list(self.session.get_inputs()[0].shape)

    def _validate_input_tensor_shape(self, model_input: np.ndarray) -> None:
        """Fail early when the prepared tensor does not match model metadata."""
        expected_shape = self._resolve_expected_input_shape()
        actual_shape = list(model_input.shape)

        if len(expected_shape) != len(actual_shape):
            raise ValueError(
                "Input rank mismatch: "
                f"model expects rank {len(expected_shape)} shape={expected_shape}, "
                f"got rank {len(actual_shape)} shape={actual_shape}"
            )

        mismatches: list[str] = []
        for idx, expected_dim in enumerate(expected_shape):
            if isinstance(expected_dim, int) and expected_dim > 0 and expected_dim != actual_shape[idx]:
                mismatches.append(
                    f"dim[{idx}] expected {expected_dim}, got {actual_shape[idx]}"
                )

        if mismatches:
            raise ValueError(
                "Input shape mismatch: "
                f"model expects shape={expected_shape}, got shape={actual_shape}. "
                + ", ".join(mismatches)
            )

    def _build_input_tensor(self, accelerometer, gyroscope) -> np.ndarray:
        """Convert axis arrays into the model's `[time, batch, channel]` tensor."""
        acc = [
            accelerometer["x"],
            accelerometer["y"],
            accelerometer["z"],
        ]
        gyro = [
            gyroscope["x"],
            gyroscope["y"],
            gyroscope["z"],
        ]

        if self.input_layout == "accel_then_gyro":
            channels = acc + gyro
        elif self.input_layout == "gyro_then_accel":
            channels = gyro + acc
        else:
            raise ValueError(
                f"Unsupported input_layout={self.input_layout!r}. "
                "Expected 'accel_then_gyro' or 'gyro_then_accel'."
            )

        data = np.array(channels, dtype=np.float32)

        if self.temporal_preprocess == "none":
            processed = data
        elif self.temporal_preprocess == "downsample2":
            processed = data[:, ::2]
        elif self.temporal_preprocess == "meanpool2":
            if data.shape[1] % 2 != 0:
                raise ValueError(
                    "meanpool2 requires an even number of timesteps, "
                    f"got shape={data.shape}"
                )
            processed = data.reshape(data.shape[0], -1, 2).mean(axis=2)
        else:
            raise ValueError(
                f"Unsupported temporal_preprocess={self.temporal_preprocess!r}. "
                "Expected 'none', 'downsample2', or 'meanpool2'."
            )

        return np.expand_dims(processed.swapaxes(1, 0), 1).astype(np.float32)

    def _aggregate_scores(self, scores: np.ndarray) -> np.ndarray:
        """Reduce sequence-level model scores to one score per activity class."""
        if self.score_aggregation == "sum":
            if scores.ndim == 3:
                return np.sum(scores, axis=(0, 1))
            if scores.ndim == 2:
                return np.sum(scores, axis=0)
            if scores.ndim == 1:
                return scores
        elif self.score_aggregation == "last":
            if scores.ndim == 3:
                return scores[-1, 0, :]
            if scores.ndim == 2:
                return scores[-1, :]
            if scores.ndim == 1:
                return scores
        elif self.score_aggregation == "mean":
            if scores.ndim == 3:
                return np.mean(scores, axis=(0, 1))
            if scores.ndim == 2:
                return np.mean(scores, axis=0)
            if scores.ndim == 1:
                return scores

        raise ValueError(
            f"Unsupported score_aggregation={self.score_aggregation!r} "
            f"for output shape={scores.shape}"
        )

    def initialize(self):
        """Create the ONNX Runtime session and validate label compatibility."""
        session_options = SessionOptions()
        session_options.execution_mode = ExecutionMode.ORT_SEQUENTIAL
        session_options.graph_optimization_level = GraphOptimizationLevel.ORT_ENABLE_ALL
        session_options.inter_op_num_threads = 1
        session_options.intra_op_num_threads = 1
        session_options.enable_mem_pattern = True
        session_options.enable_cpu_mem_arena = False
        session_options.enable_mem_reuse = True
        # Use deterministic CPU settings because this service runs in small
        # containers and should produce repeatable validation results.
        self.session = InferenceSession(self.model_path, sess_options=session_options)
        output_classes = self._resolve_output_classes()
        input_shape = self._resolve_expected_input_shape()

        if output_classes is not None and len(self.activity_labels) != output_classes:
            raise ValueError(
                "Label count mismatch: "
                f"model output expects {output_classes}, got {len(self.activity_labels)} labels. "
                f"Loaded labels={self.activity_labels!r}"
            )

        self._debug_print("expected input shape:", input_shape)
        self._debug_print("model output classes:", output_classes)
        self._debug_print("input layout:", self.input_layout)
        self._debug_print("temporal preprocess:", self.temporal_preprocess)
        self._debug_print("score aggregation:", self.score_aggregation)

    def execute_inference(self, accelerometer, gyroscope):
        """Run one inference call and return prediction details."""
        if self.session is None:
            raise RuntimeError("Inference session is not initialized")

        model_input = self._build_input_tensor(accelerometer, gyroscope)

        input_meta = self.session.get_inputs()[0]
        self._debug_print("input name:", input_meta.name)
        self._debug_print("expected input shape:", input_meta.shape)
        self._debug_print("expected input type:", input_meta.type)
        self._debug_print("actual model_input shape:", model_input.shape)
        self._debug_print("actual model_input dtype:", model_input.dtype)
        self._validate_input_tensor_shape(model_input)

        inference_inputs = {input_meta.name: model_input}
        output = self.session.run(None, inference_inputs)

        self._debug_print("number of outputs:", len(output))
        self._debug_print("output[0] shape:", output[0].shape)
        self._debug_print("output[0] dtype:", output[0].dtype)
        self._debug_print("labels count:", len(self.activity_labels))

        scores = np.array(output[0])
        class_scores = self._aggregate_scores(scores)

        self._debug_print("class_scores shape:", class_scores.shape)
        self._debug_print("class_scores:", class_scores)

        pred_class = int(np.argmax(class_scores))
        self._debug_print("pred_class:", pred_class)

        if pred_class >= len(self.activity_labels):
            raise ValueError(
                f"Predicted class index {pred_class} exceeds labels count {len(self.activity_labels)}. "
                f"Output shape={scores.shape}, class_scores shape={class_scores.shape}"
            )

        prob_class = softmax(class_scores) * 100
        prob_class = np.round(prob_class, decimals=2)

        top_k = min(self.top_k, len(self.activity_labels))
        top_indices = np.argsort(class_scores)[::-1][:top_k]

        result = {
            "predicted_label": self.activity_labels[pred_class],
            "predicted_idx": pred_class,
            "confidence": float(prob_class[pred_class]),
            "all_probs": {
                self.activity_labels[i]: float(prob_class[i])
                for i in range(len(self.activity_labels))
            },
            "top_k": [
                (self.activity_labels[i], float(prob_class[i]))
                for i in top_indices
            ],
            "raw_scores": class_scores.tolist(),
            "output_shape": list(scores.shape),
        }

        self.last_result = result
        self._debug_print(
            f"Predicted class: {result['predicted_label']} - Probabilities: {prob_class}"
        )
        self.cb(result["predicted_label"])
        return result

    def default_callback(self, activity):
        """Default callback used by legacy callers that expect print output."""
        print(activity)
