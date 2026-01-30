## 2026-01-30 - [PaddleOCR ONNX Issue]
**Learning:** Local PaddleOCR models are incompatible with `use_onnx=True` and cause `INVALID_PROTOBUF` errors. `use_onnx=False` MUST be used.
**Action:** Always check ONNX compatibility when updating PaddleOCR or models. Ensure `use_onnx=False` is set in initialization.
