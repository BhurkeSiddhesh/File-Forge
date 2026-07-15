# File-Forge: ARM-Compatible OCR Migration Proposal

## 1. Executive Summary

**Goal:** Make File-Forge deployable on ARM64 hosts (e.g., Oracle Cloud A1 Flex / Ampere) by replacing the hard dependency on PaddlePaddle/PaddleOCR with an ARM-native OCR backend, while preserving the existing x86 AI Layout Recovery path as an optional high-quality backend.

**Why:** PaddlePaddle does not officially support `arm64`. The current repo requires `paddlepaddle==2.6.2` and `paddleocr>=2.6,<3.0`, which makes ARM deployment impossible without compiling Paddle from source. The rest of the stack (FastAPI, PyMuPDF, pikepdf, Pillow, etc.) already runs on ARM64.

**Proposed default on ARM:** [RapidOCR](https://github.com/RapidAI/RapidOCR) (ONNX Runtime, ~20 MB models, near-Paddle accuracy, pure `pip install` on ARM64).

**Out of scope for the agent:** hosting setup, DNS, TLS, CI/CD secrets — you will handle those.

---

## 2. Current State

Paddle is used in three places:

| Location | Function |
|----------|----------|
| `scripts/pdf_utils.py::get_paddle_engine()` | Loads PPStructure ONNX models for layout recovery |
| `scripts/pdf_utils.py::_extract_text_with_paddle_ocr()` | OCR fallback when a PDF has no embedded text |
| `scripts/pdf_utils.py::pdf_to_word_paddle()` | AI Layout Recovery PDF → DOCX conversion |

Hard dependencies in `requirements.txt`:

```text
paddlepaddle==2.6.2
paddleocr>=2.6,<3.0
```

`Dockerfile` installs Paddle from the official mirror and runs a `WARMUP_AI=1` smoke test that calls `get_paddle_engine()`.

---

## 3. Proposed Target State

Introduce an **OCR backend abstraction** so the app can run on ARM64 without Paddle, while Paddle remains available as an optional backend on x86.

```
Environment: OCR_BACKEND=paddle  →  use PaddleOCR/PPStructure (best quality, x86 only)
Environment: OCR_BACKEND=rapidocr →  use RapidOCR (ARM64 default, good quality)
Environment: DISABLE_AI=1        →  no AI/OCR features, lightweight image
```

### Feature mapping after migration

| Feature | Current Backend | New Behavior |
|---------|-----------------|--------------|
| PDF to Text (OCR fallback) | PaddleOCR | RapidOCR by default; Paddle if `OCR_BACKEND=paddle` |
| AI Layout Recovery (PDF → DOCX) | PaddleOCR PPStructure | Paddle if available; otherwise RapidOCR + pdf2docx heuristic fallback |
| Standard PDF → DOCX | pdf2docx | unchanged |
| All other tools | non-Paddle | unchanged |

---

## 4. Exact Implementation Steps

### Phase 0 — Prep & safety (1–2 hours)

1. **Create a feature branch** from `main`:
   ```bash
   git checkout -b feat/arm-ocr-backend
   ```

2. **Add/update tests baseline.** Run the existing test suite and ensure it passes before making changes:
   ```bash
   python -m pytest
   ```

3. **Pin a temporary `DISABLE_AI=1` smoke test.** Verify the app currently starts and serves non-AI endpoints when `DISABLE_AI=1`.

### Phase 1 — Build the OCR abstraction layer (3–4 hours)

4. **Create `scripts/ocr_engine.py`.** It must expose a single interface used by `pdf_utils.py`.

   ```python
   # scripts/ocr_engine.py
   from abc import ABC, abstractmethod
   from pathlib import Path
   from typing import List, Dict, Any, Optional
   import logging

   logger = logging.getLogger(__name__)

   class OCREngine(ABC):
       @abstractmethod
       def recognize(self, image_path_or_array) -> List[Dict[str, Any]]:
           """Return list of dicts: [{"text": str, "bbox": [...], "confidence": float}, ...]"""
           ...

       @abstractmethod
       def recover_layout(self, image_path_or_array) -> List[Dict[str, Any]]:
           """Return structured layout elements (text, tables, etc.). Optional."""
           ...

       @property
       @abstractmethod
       def name(self) -> str:
           ...

   class RapidOCREngine(OCREngine):
       def __init__(self):
           from rapidocr import RapidOCR
           self._engine = RapidOCR()

       @property
       def name(self) -> str:
           return "rapidocr"

       def recognize(self, image_path_or_array):
           result, _ = self._engine(image_path_or_array)
           # Normalize RapidOCR output to the common schema
           return [
               {"text": item[1], "confidence": float(item[2]), "bbox": item[0]}
               for item in (result or [])
           ]

       def recover_layout(self, image_path_or_array):
           # RapidOCR does not do full layout recovery; treat recognize() as fallback.
           return self.recognize(image_path_or_array)

   class PaddleOCREngine(OCREngine):
       def __init__(self):
           # Refactor existing get_paddle_engine() logic into this class.
           from paddleocr import PPStructure
           ...

       @property
       def name(self) -> str:
           return "paddle"

       def recognize(self, image_path_or_array):
           result = self._engine(image_path_or_array)
           return [{"text": item.get("text"), "confidence": ..., "bbox": ...} for item in result]

       def recover_layout(self, image_path_or_array):
           return self._engine(image_path_or_array)

   def get_ocr_engine(backend: Optional[str] = None) -> Optional[OCREngine]:
       backend = backend or os.environ.get("OCR_BACKEND", "rapidocr").lower()
       if backend == "paddle":
           return PaddleOCREngine()
       if backend == "rapidocr":
           return RapidOCREngine()
       if backend in ("", "none"):
           return None
       raise ValueError(f"Unknown OCR_BACKEND: {backend}")
   ```

5. **Move Paddle-specific environment variables** from the top of `scripts/pdf_utils.py` into `PaddleOCREngine.__init__()` so they are only set when Paddle is actually loaded.

### Phase 2 — Refactor `scripts/pdf_utils.py` (4–6 hours)

6. **Replace `_extract_text_with_paddle_ocr()`** with `_extract_text_with_ocr()`:
   - Accepts a `fitz.Document`.
   - Uses the active `OCREngine` from `scripts/ocr_engine.py`.
   - Renders each page at 200 DPI, runs OCR, joins snippets with newlines.

7. **Replace `pdf_to_word_paddle()`** with `pdf_to_word_ai()`:
   - If `OCR_BACKEND=paddle` and Paddle is installed, run the existing PPStructure recovery path.
   - If `OCR_BACKEND=rapidocr`, run a new fallback path:
     - Render each page to image.
     - Run RapidOCR.
     - Insert recognized text blocks into a DOCX in reading order.
     - This preserves the spirit of "AI recovery" without Paddle.
   - If `DISABLE_AI=1`, raise a clear `HTTPException` / `ValueError` telling the user to use standard conversion.

8. **Update `extract_pdf_text()`** to call `_extract_text_with_ocr()` instead of `_extract_text_with_paddle_ocr()`.

9. **Delete vendored Paddle ONNX models** from `models/` **only if** they are no longer used. If Paddle remains optional, keep them but do not require them at build time. Recommended: keep them but fetch/download on demand for the Paddle backend.

### Phase 3 — Update dependencies (1–2 hours)

10. **Modify `requirements.txt`:**
    - Remove `paddlepaddle==2.6.2`.
    - Remove `paddleocr>=2.6,<3.0`.
    - Add `rapidocr` and ensure `onnxruntime` is present.
    - Keep everything else unchanged.

11. **Create `requirements-ai-paddle.txt`** (optional Paddle backend):
    ```text
    -r requirements.txt
    paddlepaddle==2.6.2
    paddleocr>=2.6,<3.0
    ```

### Phase 4 — Update Docker build (2–3 hours)

12. **Rewrite `Dockerfile` to support build args:**

    ```dockerfile
    FROM python:3.10

    ENV PYTHONDONTWRITEBYTECODE=1
    ENV PYTHONUNBUFFERED=1

    RUN apt-get update && apt-get install -y \
        build-essential \
        libgl1 \
        libglib2.0-0 \
        libgomp1 \
        libsm6 \
        libxext6 \
        libxrender-dev \
        tesseract-ocr \
        && rm -rf /var/lib/apt/lists/*

    WORKDIR /app
    RUN pip install --no-cache-dir --upgrade pip setuptools wheel

    # Default backend: rapidocr (ARM64-compatible)
    ARG OCR_BACKEND=rapidocr
    ENV OCR_BACKEND=${OCR_BACKEND}

    COPY requirements.txt .
    RUN pip install --no-cache-dir -r requirements.txt

    # Optional Paddle backend (x86 only)
    RUN if [ "$OCR_BACKEND" = "paddle" ]; then \
          pip install paddlepaddle==2.6.2 -i https://www.paddlepaddle.org.cn/packages/stable/cpu/ && \
          pip install "paddleocr>=2.6,<3.0"; \
        fi

    COPY . .

    ARG WARMUP_AI=0
    RUN if [ "$WARMUP_AI" = "1" ]; then \
          python -c "from scripts.ocr_engine import get_ocr_engine; e=get_ocr_engine(); print(f'{e.name if e else \"no-ai\"} engine loaded OK')"; \
        fi

    RUN mkdir -p uploads outputs && chmod 777 uploads outputs

    CMD uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000}
    ```

13. **Add build profiles to README / AGENTS.md:**
    ```bash
    # Lightweight, no AI
    docker build --build-arg OCR_BACKEND=none .

    # ARM64 AI (default)
    docker build --build-arg OCR_BACKEND=rapidocr --build-arg WARMUP_AI=1 .

    # x86 best-quality AI
    docker build --build-arg OCR_BACKEND=paddle --build-arg WARMUP_AI=1 .
    ```

### Phase 5 — Update `main.py` (1–2 hours)

14. **Modify `startup_event()`:**
    - Only warm up AI if `DISABLE_AI=0`.
    - Warm up the configured backend via `scripts.ocr_engine.get_ocr_engine()` instead of `get_paddle_engine()`.
    - Log which backend was loaded.

15. **Update the `AI_DISABLED_MESSAGE`** if needed to mention the RapidOCR fallback.

16. **Update imports** at the top of `main.py` if any function names changed (e.g., `pdf_to_word_paddle` → `pdf_to_word_ai`).

### Phase 6 — Frontend & UX (1–2 hours)

17. **Update `static/script.js`:**
    - Where the "AI Layout Recovery" checkbox is rendered, append a small note: "Uses RapidOCR on this server" or "Uses PaddleOCR on this server" depending on backend.
    - If `DISABLE_AI=1`, disable/hide the checkbox as today.

18. **Update `static/index.html` help text** if it claims Paddle specifically.

### Phase 7 — Tests (3–4 hours)

19. **Add `tests/test_ocr_engine.py`:**
    - Test `RapidOCREngine` initialization on the current architecture.
    - Test `recognize()` returns expected schema.
    - Test `get_ocr_engine("paddle")` returns `PaddleOCREngine` when installed.
    - Test `get_ocr_engine("rapidocr")` returns `RapidOCREngine`.
    - Test `get_ocr_engine("none")` returns `None`.

20. **Update `tests/test_pdf_utils.py`:**
    - Replace any direct Paddle mock with the abstraction.
    - Add a test for OCR fallback in `extract_pdf_text()` using a scanned PDF fixture.

21. **Update CI `.github/workflows/*.yml`:**
    - Add a job matrix entry for `OCR_BACKEND=rapidocr` and `DISABLE_AI=1`.
    - Keep the existing Paddle/x86 job if desired.
    - Add a Docker build smoke test with `--build-arg OCR_BACKEND=rapidocr`.

### Phase 8 — Cleanup & docs (1–2 hours)

22. **Update `AGENTS.md`:**
    - Add the new OCR abstraction pattern.
    - Document the `OCR_BACKEND` and `DISABLE_AI` env vars.
    - Log the change in the Change Log section.

23. **Update `README.md`:**
    - Replace Paddle-specific AI instructions with backend options.
    - Add ARM64 deployment notes.

24. **Run the full test suite and linter** one final time.

25. **Open a PR** with a clear description and migration notes.

---

## 5. New / Changed Files

| File | Change |
|------|--------|
| `scripts/ocr_engine.py` | **New.** Backend abstraction + RapidOCR + Paddle engines. |
| `scripts/pdf_utils.py` | Refactor OCR/layout functions to use abstraction. |
| `requirements.txt` | Remove Paddle; add RapidOCR. |
| `requirements-ai-paddle.txt` | **New.** Optional Paddle backend dependencies. |
| `Dockerfile` | Build-arg-driven backend selection. |
| `main.py` | Warm up configured backend; update imports. |
| `static/script.js` | Minor UX labels. |
| `tests/test_ocr_engine.py` | **New.** Unit tests for abstraction. |
| `tests/test_pdf_utils.py` | Update mocks and add OCR fallback test. |
| `.github/workflows/*.yml` | Add rapidocr/disable-ai matrix. |
| `AGENTS.md` | Document new patterns. |
| `README.md` | Update AI/backend docs. |

---

## 6. Testing Plan

| Test | Command / Step | Expected Result |
|------|----------------|-----------------|
| Non-AI image builds | `docker build --build-arg OCR_BACKEND=none .` | Success, no OCR deps installed. |
| ARM AI image builds | `docker build --build-arg OCR_BACKEND=rapidocr --build-arg WARMUP_AI=1 .` | Success, engine loads OK. |
| x86 AI image builds | `docker build --build-arg OCR_BACKEND=paddle --build-arg WARMUP_AI=1 .` | Success on x86_64. |
| App starts with `DISABLE_AI=1` | `DISABLE_AI=1 python main.py` | Uvicorn starts, non-AI endpoints work. |
| App starts with RapidOCR | `OCR_BACKEND=rapidocr python main.py` | Engine warms up, text extraction works. |
| PDF text extraction fallback | Upload scanned PDF to `/api/pdf/extract-text` | Text returned without Paddle. |
| AI Layout Recovery fallback | Upload scanned PDF with AI mode on ARM | DOCX produced via RapidOCR heuristic. |
| Existing unit tests | `python -m pytest` | All pass. |

---

## 7. Acceptance Criteria

- [ ] `docker build` succeeds on an ARM64 host with `OCR_BACKEND=rapidocr`.
- [ ] The app starts and passes health checks without Paddle installed.
- [ ] PDF text extraction works on scanned PDFs using RapidOCR.
- [ ] AI Layout Recovery produces a DOCX on ARM64 (quality may be lower than Paddle).
- [ ] Paddle backend still works on x86_64 when `OCR_BACKEND=paddle`.
- [ ] `DISABLE_AI=1` image has no OCR dependencies and starts instantly.
- [ ] All existing non-AI features continue to work.
- [ ] CI passes for at least `rapidocr` and `none` backends.

---

## 8. Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| RapidOCR accuracy lower than Paddle for tables | Document the limitation; keep Paddle as x86 option; future iteration can add docTR/Surya. |
| RapidOCR model download fails at runtime | Pin model URLs / vendoring; add retry logic; or bundle models in Docker layer. |
| Frontend breaks due to renamed endpoints | Keep route signatures unchanged; only internal function names change. |
| Tests mock Paddle internals | Update mocks to target `OCREngine` methods instead of Paddle directly. |
| Dockerfile grows complex | Use build args, clear comments, and separate requirements files. |

---

## 9. Suggested Agent Prompt

You can hand the following to the agent:

> Implement the ARM64 OCR migration for File-Forge. Create `scripts/ocr_engine.py` with `RapidOCREngine` and `PaddleOCREngine` behind an `OCREngine` abstraction. Refactor `scripts/pdf_utils.py` so `_extract_text_with_paddle_ocr()` becomes `_extract_text_with_ocr()` and `pdf_to_word_paddle()` becomes `pdf_to_word_ai()`. Remove Paddle from `requirements.txt` and add `rapidocr`. Create `requirements-ai-paddle.txt` for the optional x86 backend. Update the `Dockerfile` to accept `OCR_BACKEND={none|rapidocr|paddle}` and `WARMUP_AI`. Update `main.py` startup warmup to use the abstraction. Add `tests/test_ocr_engine.py`. Update CI to test `OCR_BACKEND=rapidocr` and `DISABLE_AI=1`. Update `AGENTS.md` and `README.md`. Do not change hosting, DNS, or Render config. Ensure all existing tests pass.
