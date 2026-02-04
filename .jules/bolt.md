## 2026-02-04 - PaddleOCR ONNX Loading Quirk
**Learning:** When initializing `PPStructure` with `use_onnx=True`, passing a directory path (e.g., `layout_model_dir`) causes `onnxruntime` to fail with `INVALID_PROTOBUF` if the directory contains Paddle models but `paddleocr` doesn't automatically append `model.onnx` or if the directory structure isn't exactly what it expects.
**Action:** Explicitly point to the `model.onnx` file (e.g., `str(path / "model.onnx")`) when initializing `PPStructure` with `use_onnx=True`.
