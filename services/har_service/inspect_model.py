"""
Standalone script to inspect the ONNX model metadata.
Run locally (no Docker needed); it only requires onnxruntime.

This tells us:
  - Exact input shape the model expects
  - Exact output shape, which reveals how many classes the model predicts
"""

import sys
from pathlib import Path

try:
    import onnxruntime as ort
except ImportError:
    print("ERROR: onnxruntime not installed. Run: pip install onnxruntime")
    sys.exit(1)

try:
    import onnx
    HAS_ONNX = True
except ImportError:
    HAS_ONNX = False

MODEL_PATH = Path(__file__).parent / "model" / "L2MU_plain_leaky.onnx"


def inspect_with_onnxruntime(model_path: str) -> None:
    """Print input/output metadata using ONNX Runtime."""
    print("=" * 60)
    print("ONNX Runtime Inspection")
    print("=" * 60)

    session = ort.InferenceSession(model_path)

    print("\n--- INPUTS ---")
    for inp in session.get_inputs():
        print(f"  Name : {inp.name}")
        print(f"  Shape: {inp.shape}")
        print(f"  Type : {inp.type}")
        print()

    print("--- OUTPUTS ---")
    for out in session.get_outputs():
        print(f"  Name : {out.name}")
        print(f"  Shape: {out.shape}")
        print(f"  Type : {out.type}")
        print()

    # Try a dummy inference to get a concrete output shape for dynamic models.
    import numpy as np

    inp_meta = session.get_inputs()[0]
    # Build a dummy input matching the expected shape
    # Replace dynamic dims (None / strings) with concrete sizes
    dummy_shape = []
    for dim in inp_meta.shape:
        if isinstance(dim, int):
            dummy_shape.append(dim)
        else:
            dummy_shape.append(1)  # batch size or dynamic dim

    print(f"--- DUMMY INFERENCE (input shape={dummy_shape}) ---")
    dummy_input = np.zeros(dummy_shape, dtype=np.float32)
    outputs = session.run(None, {inp_meta.name: dummy_input})

    for i, out_arr in enumerate(outputs):
        print(f"  output[{i}] shape: {out_arr.shape}")
        print(f"  output[{i}] dtype: {out_arr.dtype}")
        if out_arr.ndim <= 2:
            print(f"  output[{i}] values: {out_arr}")
        print()

    # Determine number of classes
    final_output = outputs[-1]
    if final_output.ndim == 2:
        num_classes = final_output.shape[-1]
    elif final_output.ndim == 1:
        num_classes = final_output.shape[0]
    elif final_output.ndim == 3:
        num_classes = final_output.shape[-1]
    else:
        num_classes = "UNKNOWN"

    print(f">>> CONCLUSION: Model appears to have {num_classes} output classes <<<")
    print()


def inspect_with_onnx(model_path: str) -> None:
    """Print lower-level graph metadata when the optional onnx package exists."""
    if not HAS_ONNX:
        print("(Skipping onnx graph inspection; pip install onnx for more detail)")
        return

    print("=" * 60)
    print("ONNX Graph Inspection")
    print("=" * 60)

    model = onnx.load(model_path)
    print(f"  IR version : {model.ir_version}")
    opset_strs = [f"{o.domain or 'ai.onnx'}:{o.version}" for o in model.opset_import]
    print(f"  Opset      : {opset_strs}")
    print(f"  Producer   : {model.producer_name} {model.producer_version}")
    print(f"  Graph name : {model.graph.name}")

    print(f"\n  Inputs ({len(model.graph.input)}):")
    for inp in model.graph.input:
        shape = [d.dim_value if d.dim_value else d.dim_param for d in inp.type.tensor_type.shape.dim]
        print(f"    {inp.name}: {shape}")

    print(f"\n  Outputs ({len(model.graph.output)}):")
    for out in model.graph.output:
        shape = [d.dim_value if d.dim_value else d.dim_param for d in out.type.tensor_type.shape.dim]
        print(f"    {out.name}: {shape}")

    print(f"\n  Total nodes: {len(model.graph.node)}")
    print()


if __name__ == "__main__":
    path = str(MODEL_PATH)
    if not MODEL_PATH.exists():
        print(f"Model not found at: {path}")
        sys.exit(1)

    print(f"Model: {path}\n")
    inspect_with_onnx(path)
    inspect_with_onnxruntime(path)
