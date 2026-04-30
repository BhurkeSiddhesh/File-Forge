# File Forge

**File Forge** is an all-in-one, web-based file manipulation tool. Upload a file, process it in seconds, and download the result — no software installation required.

**Live App:** [https://file-forge.onrender.com](https://file-forge.onrender.com)

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/BhurkeSiddhesh/File-Forge?utm_source=oss&utm_medium=github&utm_campaign=BhurkeSiddhesh%2FFile-Forge&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)

---

## Features

### PDF Tools
| Feature | Description |
|---|---|
| **Remove Password** | Unlock password-protected PDF files instantly |
| **Convert to Word (Standard)** | Fast PDF → DOCX conversion using `pdf2docx` |
| **Convert to Word (AI Layout Recovery)** | High-fidelity conversion using PaddleOCR — preserves tables, columns, and complex layouts |
| **Extract Pages** | Pull specific pages or page ranges (e.g. `1,3,5-10`) out of a PDF into a new file |

### Image Tools
| Feature | Description |
|---|---|
| **HEIC → JPEG** | Convert Apple HEIC/HEIF photos to universally compatible JPEG |
| **Resize Image** | Resize by exact dimensions, percentage, or target file size (KB) |
| **Crop Image** | Crop images using a visual drag-and-drop cropper (powered by Cropper.js) |

### Workflow Builder
Chain multiple operations into a single pipeline. Example: unlock a PDF, then convert it to Word — all in one step with real-time progress streaming via Server-Sent Events (SSE).

---

## Tech Stack

- **Backend**: Python 3.10+, [FastAPI](https://fastapi.tiangolo.com/), Uvicorn
- **PDF Processing**: `pikepdf`, `pdf2docx`, `PaddleOCR` (PPStructure), `PyMuPDF`
- **Image Processing**: `Pillow`, `pillow-heif`
- **Frontend**: Vanilla HTML/CSS/JS, [Cropper.js](https://fengyuanchen.github.io/cropperjs/)
- **Deployment**: [Render](https://render.com/), Docker

---

## Project Structure

```
File-Forge/
├── main.py                  # FastAPI app — all API routes
├── requirements.txt         # Python dependencies
├── Dockerfile               # Container build config
├── render.yaml              # One-click Render deployment config
├── scripts/
│   ├── pdf_utils.py         # PDF password removal, conversion, page extraction
│   ├── image_utils.py       # HEIC conversion, resize, crop
│   ├── utils.py             # Shared helpers
│   ├── security_utils.py    # Input sanitization utilities
│   └── fix_models.py        # PaddleOCR ONNX model setup script
├── static/
│   ├── index.html           # Single-page frontend
│   ├── script.js            # All frontend logic
│   └── style.css            # Styles
├── models/                  # PaddleOCR ONNX model files (auto-downloaded)
├── uploads/                 # Temporary upload staging (auto-cleared)
├── outputs/                 # Processed files (auto-deleted after download)
└── tests/
    ├── conftest.py           # Fixtures (mock PDFs, test client setup)
    ├── test_main.py          # Integration tests for API endpoints
    ├── test_pdf_utils.py     # Unit tests for PDF processing logic
    ├── test_image_utils.py   # Unit tests for image processing logic
    └── ...                  # Additional benchmarks and edge-case tests
```

---

## API Reference

All endpoints accept `multipart/form-data`. Authentication is via `X-API-Key` header (only enforced when `FILE_FORGE_API_KEY` env var is set; omit in local dev).

### PDF Endpoints

#### `POST /api/pdf/remove-password`
Remove the password from a protected PDF.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The PDF file |
| `password` | string | Yes | The PDF password |

#### `POST /api/pdf/convert-to-word`
Convert a PDF to DOCX format.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The PDF file |
| `use_ai` | bool | No | Use PaddleOCR for layout-aware conversion (default: `false`) |
| `password` | string | No | Password if the PDF is encrypted |

#### `POST /api/pdf/extract-pages`
Extract a subset of pages from a PDF.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The PDF file |
| `pages` | string | Yes | Comma-separated pages or ranges, e.g. `1,3,5-10` |
| `password` | string | No | Password if the PDF is encrypted |

### Image Endpoints

#### `POST /api/image/heic-to-jpeg`
Convert a HEIC/HEIF image to JPEG.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The HEIC/HEIF image |
| `quality` | int | No | JPEG quality 1–95 (default: `95`) |

#### `POST /api/image/resize`
Resize an image.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The image |
| `mode` | string | Yes | `dimensions`, `percentage`, or `target_size` |
| `width` | int | No | Target width (for `dimensions` mode) |
| `height` | int | No | Target height (for `dimensions` mode) |
| `percentage` | int | No | Scale factor (for `percentage` mode) |
| `target_size_kb` | int | No | Target file size in KB (for `target_size` mode) |

#### `POST /api/image/crop`
Crop an image to a rectangle.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The image |
| `x` | int | Yes | Left edge of crop box |
| `y` | int | Yes | Top edge of crop box |
| `width` | int | Yes | Width of crop box |
| `height` | int | Yes | Height of crop box |

### Workflow Endpoint

#### `POST /api/workflow/execute`
Execute a multi-step pipeline on a file. Returns a **Server-Sent Events (SSE)** stream with real-time progress.

| Field | Type | Required | Description |
|---|---|---|---|
| `file` | File | Yes | The input file |
| `steps` | JSON string | Yes | Array of step objects (see below) |

**Step object format:**
```json
[
  { "type": "remove_password", "label": "Unlock PDF", "config": { "password": "secret" } },
  { "type": "pdf_to_word",     "label": "Convert to Word", "config": { "use_ai": false } }
]
```

Available `type` values: `remove_password`, `pdf_to_word`, `heic_to_jpeg`, `resize_image`, `crop_image`.

### Download Endpoint

#### `GET /api/download/{filename}`
Download a processed file. The file is **automatically deleted** from the server after download.

---

## Getting Started (Local Development)

### Prerequisites

- Python 3.10+
- pip

### Installation

```bash
git clone https://github.com/BhurkeSiddhesh/File-Forge.git
cd File-Forge
pip install -r requirements.txt
```

### Run the Server

```bash
python main.py
```

The app will be available at [http://127.0.0.1:8001](http://127.0.0.1:8001).

### Environment Variables

| Variable | Description | Default |
|---|---|---|
| `PORT` | Port the server listens on | `8001` |
| `FILE_FORGE_API_KEY` | API key for authentication (leave unset to disable auth in dev) | _(none)_ |

---

## Running Tests

This project uses `pytest`. Run the full test suite with:

```bash
python -m pytest
```

Key test files:
- [`tests/conftest.py`](tests/conftest.py) — fixtures including auto-generated mock PDFs
- [`tests/test_main.py`](tests/test_main.py) — integration tests for all API endpoints
- [`tests/test_pdf_utils.py`](tests/test_pdf_utils.py) — unit tests for PDF processing logic
- [`tests/test_image_utils.py`](tests/test_image_utils.py) — unit tests for image processing logic

Tests create and clean up all temporary files automatically.

---

## Deployment

### Deploy to Render (Recommended)

1. **Fork** this repository and log in to [Render](https://render.com/).
2. **Connect** your GitHub repository.
3. Render will auto-detect [`render.yaml`](render.yaml) and configure the service.
4. Click **Deploy**.

> [!IMPORTANT]
> This app uses **PaddleOCR** for high-quality PDF conversion, which requires at least **1 GB of RAM**. The Render **Starter** plan or higher is required. The Free Tier (512 MB) will crash during AI model initialization.

### Deploy with Docker

```bash
docker build -t file-forge .
docker run -p 8001:8001 file-forge
```

### GitHub Pages

GitHub Pages is **not supported** — it only serves static files and cannot run the Python backend. Use Render, Railway, Fly.io, or any platform that supports Docker or Python WSGI/ASGI apps.
