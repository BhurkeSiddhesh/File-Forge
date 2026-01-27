# File Forge - Workspace Instructions

> **Note**: Always read and update the Change Log section BEFORE committing changes.

## 1. Tech Stack

- **Backend**: Python 3.10+
- **PDF Processing**: pikepdf

## 2. Project Structure & File Placement

- **Root**: Configs only (`requirements.txt`).
- **Scripts**: Python scripts in root directory.

## 3. Code Patterns

- **Architecture**: Simple CLI scripts with argparse.
- **Error Handling**: Always catch and display user-friendly error messages.
- **Type Hints**: Use type hints for function signatures.

## 4. Active Context

- **Current Sprint**: PDF password removal utility

## 5. Change Log (Reverse Chronological)

> **CRITICAL**: Add entry here BEFORE every commit.

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

### 2026-01-23

- **feat**: Initial PDF password remover script
- **Files**: `pdf_password_remover.py`, `requirements.txt`
- **Verification**: Manual testing with password-protected PDF
