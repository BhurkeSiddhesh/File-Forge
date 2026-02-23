# File Forge - Workspace Instructions

> **Note**: Always read and update the Change Log section BEFORE committing changes.

## 1. Tech Stack

- **Backend**: Python 3.10+ (FastAPI)
- **Frontend**: Vanilla HTML/CSS/JS (Modern/Premium)
- **PDF Processing**: pikepdf, pdf2docx

## 2. Project Structure & File Placement

- **Root**: Configs (`requirements.txt`), main application (`main.py`).
- **Scripts**: Utility modules like `pdf_utils.py`.
- **Static**: Frontend assets in `/static`.
- **Data**: Uploads in `/uploads`, processed files in `/outputs`.

## 3. Code Patterns

- **Architecture**: Simple CLI scripts with argparse.
- **Error Handling**: Always catch and display user-friendly error messages.
- **Type Hints**: Use type hints for function signatures.

### 2026-02-03

- **feat**: Added Windows benchmark script (`tests/run_benchmark.ps1`) for cross-platform compatibility.
- **chore**: Removed developer comments from `tests/run_benchmark.sh`.
- **Files**: `tests/run_benchmark.ps1`, `tests/run_benchmark.sh`
- **Verification**: `bash tests/run_benchmark.sh` passed, manual verification of PS1 logic.

## 4. Active Context

- **Current Sprint**: Modern Web UI, PDF tools, and Image tools (HEIC to JPEG).

## 5. Change Log (Reverse Chronological)

> **CRITICAL**: Add entry here BEFORE every commit.

### 2026-02-23

- **feat**: Bulk merged 26 PRs covering accessibility, performance (PaddleOCR caching, threadpooling), and security fixes.
- **feat**: Implemented API Key Authentication (X-API-Key / api_key query param) across all processing endpoints.
- **security**: Enforced unique UUID-based filename randomization for all uploads to prevent race conditions and path traversal.
- **fix**: Resolved PaddleOCR singleton API compatibility issues and fixed `ImportError` in test environment.
- **fix**: Addressed `UnicodeEncodeError` in performance tests for Windows compatibility.
- **Files**: `main.py`, `pdf_utils.py`, `image_utils.py`, `requirements.txt`, `static/`, `tests/`
- **Verification**: All 39 tests passed (`python -m pytest tests/`).

### 2026-02-18

- **fix**: Fixed CI workflow YAML indentation - steps are now properly indented under `steps:` key
- **fix**: Removed redundant PYTHONPATH setting in pytest command (kept only in env block)
- **feat**: Added GitHub Actions CI workflow (`ci.yml`)
- **feat**: Workflow tests on Python 3.10, 3.11, and 3.12
- **feat**: Includes pip dependency caching for faster builds
- **feat**: Runs on pushes and pull requests to main/master branches
- **Files**: `.github/workflows/ci.yml`, `AGENTS.md`
- **Verification**: Workflow file syntax validated

### 2026-02-17

- **chore**: Updated `branch_list.txt` with current branch inventory.
- **Files**: `branch_list.txt`
- **Verification**: `pytest tests/` — 22 tests passed.

### 2026-02-11

- **feat**: Added PDF page extraction utility and API to save selected pages as a new PDF.
- **feat**: Exposed UI controls for selecting page ranges and downloading extracted PDFs.
- **test**: Added unit and API coverage for page extraction flows.
- **Files**: `pdf_utils.py`, `main.py`, `static/index.html`, `static/script.js`, `tests/conftest.py`, `tests/test_pdf_utils.py`, `tests/test_main.py`
- **Verification**: `PYTHONPATH=. pytest -q`

### 2026-02-05

- **refactor**: Major code duplication elimination across the codebase (~45 lines removed)
- **feat**: Created `utils.py` with common `process_uploaded_file()` and `cleanup_temp_file()` utilities
- **refactor**: Extracted `_preprocess_image()` helper in `image_utils.py` to eliminate 3x duplication of EXIF/RGB conversion
- **refactor**: Refactored all 5 API endpoints in `main.py` to use new utility functions (remove-password, convert-to-word, heic-to-jpeg, resize, crop)
- **refactor**: Consolidated error handling, file cleanup, and debug logging patterns
- **Files**: `utils.py` (new), `main.py`, `image_utils.py`, `pdf_utils.py`
- **Verification**: All 22 tests passed (`pytest tests/ -v`)

### 2026-02-05

- **feat**: Added click-to-add functionality for workflow steps to support keyboard users (replacing drag-and-drop dependency).
- **fix**: Added `role="button"`, `tabindex="0"`, and `aria-label` to workflow palette items.
- **fix**: Added focus visibility styles for step items in palette.
- **Files**: `static/index.html`, `static/script.js`, `static/style.css`
- **Verification**: Verified via Playwright script `verification/verify_workflow_a11y.py`.

### 2026-02-05

- **fix**: Merged fix for transparent image conversion (RGBA/P modes) in `image_utils.py` from `palette/a11y` branch.
- **Files**: `image_utils.py`
- **Verification**: `pytest tests/test_image_utils.py` passed.

### 2026-02-04

- **perf**: Implemented singleton pattern for `PaddleOCR` engine to eliminate model reload overhead per request.
- **refactor**: Centralized `PPStructure` initialization in `pdf_utils.py` and updated `main.py` to use it during startup.
- **test**: Added unit test `tests/test_paddle_singleton.py` to verify singleton behavior.
- **Files**: `pdf_utils.py`, `main.py`, `tests/test_paddle_singleton.py`
- **Verification**: `python tests/test_paddle_singleton.py` passed; full test suite passed.

- **feat**: Improved accessibility by adding focus styles for custom toggles and global focus indicators.
- **fix**: Added ARIA labels to workflow builder buttons.
- **Files**: `static/style.css`, `static/script.js`
- **Verification**: Playwright script verified focus states and ARIA labels.


### 2026-02-03

- **fix**: Added missing page breaks when merging recovered DOCX pages.
- **refactor**: Extracted merging logic into `merge_docx_files` helper function.
- **test**: Added unit tests for merging logic in `tests/test_docx_merge.py`.
- **Files**: `pdf_utils.py`, `tests/test_docx_merge.py`
- **Verification**: `python -m pytest tests/test_docx_merge.py` passed.

- **chore**: Updated `agency.yaml` with detailed, natural language descriptions for specialized agent roles (Architect, PDF/Image Specialists, Frontend, QA/Watchdog, Workflow Orchestrator).
- **fix**: Wrapped blocking workflow steps in `run_in_threadpool` to enable real-time SSE progress updates.
- **feat**: Enhanced workflow UI with pulsing animations for processing steps and green gradients for completed steps.
- **fix**: Added `timestamp` version query to CSS link to force cache refresh.
- **fix**: Fixed workflow password remover bug - arguments to `remove_pdf_password` were passed in wrong order (password and output_dir were swapped)
- **feat**: Added real-time workflow progress visualization with SSE streaming
- **feat**: Step cards now show animated states: pending (dimmed), processing (pulsing orange glow), completed (green)
- **fix**: Added explicit `await asyncio.sleep(1.0)` in workflow loop to ensure processing animations are visible for fast tasks.
- **feat**: Status text shows current step name and progress (e.g., "Step 1 of 3")
- **Files**: `main.py`, `static/script.js`, `static/style.css`
- **Verification**: Manual testing with workflow

### 2026-02-02

- **chore**: Verified and cleanup up merged branches (`perf-lazy-import-pikepdf`, `palette-a11y-improvements`).
- **fix**: Installed missing `pikepdf` dependency.
- **Files**: `requirements.txt`, `tests/`
- **Verification**: `python -c "import pikepdf..."` success.

### 2026-01-31

- **feat**: Added accessibility support for keyboard navigation
- **fix**: Added ARIA labels and keyboard listeners for interactive cards
- **Files**: `static/index.html`, `static/script.js`, `AGENTS.md`
- **Verification**: Manual review

### 2026-01-30

- **feat**: Merged `palette-a11y-improvements` (Accessibility fixes)
- **feat**: Merged `perf-lazy-import-pikepdf` (Lazy loading optimization)
- **Files**: `pdf_password_remover.py`, `static/style.css`

### 2026-01-30

- **feat**: Added Workflow Builder - visual drag-and-drop pipeline creator
- **feat**: New Workflow card on home page with project-diagram icon
- **feat**: Drag-and-drop step palette (Unlock PDF, PDF→Word, HEIC→JPEG, Resize)
- **feat**: Workflow canvas with arrow connectors between steps
- **feat**: Step configuration modal for password and resize settings
- **feat**: Backend `/api/workflow/execute` endpoint for chained processing
- **Files**: `main.py`, `static/index.html`, `static/script.js`, `static/style.css`, `AGENTS.md`
- **Verification**: Manual browser testing

### 2026-01-30

- **fix**: Implemented backend-assisted HEIC preview for image cropping.
- **fix**: Resolved "broken image" icon in cropping UI for HEIC files.
- **Files**: `static/script.js`

### 2026-01-30

- **fix**: Fixed image cropping issue for photos with EXIF orientation (e.g., from smartphones).
- **feat**: Added `ImageOps.exif_transpose` to `image_utils.py` to auto-rotate images before processing.
- **Files**: `image_utils.py`
- **Verification**: `pytest tests/test_image_crop.py` passed.

### 2026-01-30

- **feat**: Added comprehensive Image Resizer
- **feat**: Supported resize modes: Dimensions, Percentage, and Target File Size (KB)
- **feat**: Added new API endpoint `/api/image/resize`
- **feat**: Implemented iterative compression algorithm for target file size
- **feat**: Updated frontend with "Resize" mode and dynamic input controls
- **Files**: `image_utils.py`, `main.py`, `static/index.html`, `static/script.js`, `static/style.css`, `tests/test_image_resize.py`
- **feat**: Added Manual Image Cropping with visual UI (Cropper.js)
- **fix**: Solved "white-on-white" visibility issue in dropdowns
- **feat**: Added new API endpoint `/api/image/crop`
- **Files**: `image_utils.py`, `main.py`, `static/index.html`, `static/script.js`, `static/style.css`, `tests/test_image_crop.py`
- **Verification**: `pytest tests/test_image_crop.py` passed (3/3 tests)

### 2026-01-29

- **feat**: Added HEIC to JPEG conversion feature
- **feat**: Created `image_utils.py` with `heic_to_jpeg()` function using `pillow-heif`
- **feat**: Added `/api/image/heic-to-jpeg` endpoint in `main.py`
- **feat**: Added Image Tools section in frontend with quality slider
- **feat**: Added unit tests in `tests/test_image_utils.py` and API tests in `tests/test_main.py`
- **Files**: `image_utils.py`, `main.py`, `requirements.txt`, `static/index.html`, `static/script.js`, `static/style.css`, `tests/conftest.py`, `tests/test_main.py`, `tests/test_image_utils.py`
- **Verification**: `pytest -v` - All tests passed

### 2026-01-28

- **feat**: Merged all feature and performance branches into `pdf_updates`.
- **feat**: Resolved conflicts in `requirements.txt`, `.gitignore`, `AGENTS.md`, and `pdf_password_remover.py`.
- **feat**: Added `@jules` comments for missing features (language support, page breaks).
- **fix**: Added missing `requests` dependency required by `paddleocr`.
- **feat**: Cleaned up merged remote branches.
- **Files**: `pdf_utils.py`, `main.py`, `requirements.txt`, `.gitignore`, `AGENTS.md`

### 2026-01-27

- **feat**: Implemented premium Web UI with FastAPI backend.
- **feat**: Added PDF to DOCX conversion using `pdf2docx`.
- **feat**: Created `outputs/` folder for processed files.
- **feat**: Refactored logic into `pdf_utils.py` and `main.py`.
- **Files**: `main.py`, `pdf_utils.py`, `static/`, `outputs/`, `requirements.txt`
- **Verification**: FastAPI server running on port 8001; verified index serving.

### 2026-01-25

- **perf**: Implemented directory batch processing to amortize startup costs
- **feat**: Added support for processing all `.pdf` files in a directory
- **test**: Added benchmark infrastructure in `tests/`
- **Files**: `pdf_password_remover.py`, `tests/benchmark_setup.py`, `tests/run_benchmark.sh`
- **Verification**: `tests/run_benchmark.sh` shows ~5x speedup (2.2s -> 0.4s) for 10 files.

### 2026-01-24

- **feat**: Added `inputs` folder and interactive input prompts for file path and password
- **feat**: Made `input_pdf` and `password` optional with default values
- **fix**: Fixed SyntaxError (unicode error) in file path by using raw string
- **Files**: `pdf_password_remover.py`, `inputs/`
- **Verification**: `python pdf_password_remover.py` now prompts for input
- **Verification**: `python pdf_password_remover.py <path> <pass>` still works via CLI
- **perf**: Deferred `pikepdf` import to optimize CLI startup speed
- **Verification**: Measured ~50% reduction in startup time (0.26s -> 0.13s)

### 2026-01-23

- **feat**: Initial PDF password remover script
- **Files**: `pdf_password_remover.py`, `requirements.txt`
- **Verification**: Manual testing with password-protected PDF


### 2026-02-04

- **perf**: Optimized `api_remove_password` to run in a thread pool, preventing blocking of the main event loop.
- **Files**: `main.py`
- **Verification**: `tests/benchmark_blocking.py` showed reduction in concurrent request latency from ~0.5s (blocked) to ~0.05s (non-blocked).
