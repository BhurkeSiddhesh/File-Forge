## 2026-05-24 - PaddleOCR Initialization Strategy
**Learning:** PaddleOCR's `PPStructure` initialization is extremely expensive (~4.5s warm, up to 45s cold/downloading). Creating a new instance per request destroys performance.
**Action:** Always use a Singleton pattern for AI engines (`get_paddle_engine()`) and warm it up during application startup (`@app.on_event("startup")`).

## 2026-05-24 - PaddleOCR ONNX Compatibility
**Learning:** Local PaddlePaddle models provided in this repo are NOT compatible with `use_onnx=True`. Trying to force ONNX results in `INVALID_PROTOBUF` errors.
**Action:** Use `use_onnx=False` when working with the provided local models in `models/`.
