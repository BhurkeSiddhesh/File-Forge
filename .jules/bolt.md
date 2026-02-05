## 2026-02-04 - PaddleOCR Model Initialization Overhead
**Learning:** The `paddleocr.PPStructure` engine is extremely heavy to initialize (loading ONNX models from disk). Initializing it inside the request handler (`pdf_to_word_paddle`) caused significant latency for every request.
**Action:** Use a Singleton pattern (lazy loading) for heavy AI models. Initialize them during application startup (warmup) to ensure fast response times for users. Consolidated initialization logic into `pdf_utils.py` to avoid duplication in `main.py`.

## 2026-02-04 - Async Def Blocking Event Loop
**Learning:** Defining FastAPI path operations with `async def` but calling synchronous heavy functions (like image processing or PDF conversion) directly inside them blocks the main event loop, preventing other requests (e.g., health checks) from being processed.
**Action:** Always wrap heavy synchronous CPU-bound or blocking I/O operations in `fastapi.concurrency.run_in_threadpool` when using `async def` endpoints.
