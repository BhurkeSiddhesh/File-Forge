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

## 4. Active Context

- **Current Sprint**: Modern Web UI and expanded PDF tools (Word conversion).

## 5. Change Log (Reverse Chronological)

> **CRITICAL**: Add entry here BEFORE every commit.

### 2026-01-27

- **feat**: Implemented premium Web UI with FastAPI backend.
- **feat**: Added PDF to DOCX conversion using `pdf2docx`.
- **feat**: Created `outputs/` folder for processed files.
- **feat**: Refactored logic into `pdf_utils.py` and `main.py`.
- **Files**: `main.py`, `pdf_utils.py`, `static/`, `outputs/`, `requirements.txt`
- **Verification**: FastAPI server running on port 8001; verified index serving.

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
