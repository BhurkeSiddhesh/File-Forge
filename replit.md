# File Forge

A web-based file manipulation utility for PDF and image processing.

## Architecture

- **Backend**: Python 3.12 + FastAPI, serving both the API and static frontend files
- **Frontend**: Vanilla HTML/CSS/JavaScript with Cropper.js (served at `/static/`)
- **Entry point**: `main.py` (FastAPI app)
- **Port**: 5000

## Features

- PDF password removal (pikepdf)
- PDF to Word conversion: standard (pdf2docx) and AI-powered with layout recovery (PaddleOCR/PPStructure)
- PDF page extraction (PyMuPDF)
- PDF compression with three levels (Low/Medium/High) — PyMuPDF optimization + PIL image resampling
- HEIC to JPEG image conversion (pillow-heif)
- Image resizing and cropping (Pillow)
- Multi-step workflow pipeline with SSE progress streaming (compress_pdf step supported)

## Project Structure

```
main.py              # FastAPI routes and app entry point
scripts/
  pdf_utils.py       # PDF manipulation logic (pikepdf, pdf2docx, PaddleOCR)
  image_utils.py     # Image processing (Pillow, pillow-heif)
  fix_models.py      # PaddleOCR ONNX model download utility
  security_utils.py  # Input sanitization helpers
static/
  index.html         # Frontend SPA
  script.js          # Frontend logic (Cropper.js, fetch API)
  style.css          # Styles
uploads/             # Temp directory for uploaded files (auto-cleaned)
outputs/             # Temp directory for processed files (deleted after download)
models/              # PaddleOCR ONNX model files (downloaded on first AI use)
tests/               # pytest test suite
```

## Key Dependencies

- `fastapi` + `uvicorn` — web framework
- `pikepdf` — PDF password removal
- `pdf2docx` — standard PDF to DOCX conversion
- `PyMuPDF` (fitz) — PDF page extraction
- `paddlepaddle==2.6.2` — AI framework (installed from official mirror)
- `paddleocr==2.9.1` — OCR/layout recovery for AI Word conversion
- `onnxruntime` — ONNX model inference
- `Pillow`, `pillow-heif` — image processing
- `opencv-python-headless` — image processing (headless, no libGL required)
- `gunicorn` — production WSGI server

## Critical Environment Setup

PaddlePaddle requires `libgomp.so.1` (OpenMP runtime). The nix `gcc` package provides it. The workflow command exports `LD_LIBRARY_PATH` to point to the correct libgomp location:

```
LD_LIBRARY_PATH=/nix/store/3h9y320bxdxs0byqzkkqmbcl5yip4cf8-gcc-15.1.0-lib/lib
```

**Important**: `opencv-python` (full, GUI version) must NOT be installed — it requires `libGL.so.1` which is unavailable. Only `opencv-python-headless` is compatible.

**Important**: numpy must be `<2.0` for PaddleOCR 2.9.1 compatibility.

## Workflow

- **Start application**: `export LD_LIBRARY_PATH=... && uvicorn main:app --host 0.0.0.0 --port 5000`

## Authentication

API key authentication via `X-API-Key` header. If `FILE_FORGE_API_KEY` env var is not set, all requests are allowed (dev mode).

## AI Models

PaddleOCR models are downloaded on first use of the AI Word conversion feature. They are stored in `models/`. The startup event warms up the models (may fail gracefully if models aren't pre-downloaded).
