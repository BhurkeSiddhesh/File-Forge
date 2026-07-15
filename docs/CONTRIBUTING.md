# Contributing to File Forge

Thank you for your interest in contributing to File Forge! This document outlines our development process.

## Branch Flow

1. Create a branch from `main` for your feature or bugfix. Name it descriptively (e.g., `feature/add-new-tool` or `fix/issue-123`).
2. Make your changes in the branch. Keep your commits atomic and focused.
3. Open a Pull Request against the `main` branch.

## Commit Style

We follow the [Conventional Commits](https://www.conventionalcommits.org/en/v1.0.0/) specification:

*   `feat:` A new feature
*   `fix:` A bug fix
*   `docs:` Documentation only changes
*   `style:` Changes that do not affect the meaning of the code (white-space, formatting, missing semi-colons, etc)
*   `refactor:` A code change that neither fixes a bug nor adds a feature
*   `perf:` A code change that improves performance
*   `test:` Adding missing tests or correcting existing tests
*   `chore:` Changes to the build process or auxiliary tools and libraries such as documentation generation

## Development Setup

1. Fork and clone the repository.
2. Create a virtual environment and install the dependencies:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # Or .venv\Scripts\activate on Windows
   pip install -r requirements.txt
   pip install pre-commit pytest pytest-cov
   ```
3. Set up pre-commit hooks (this will automatically run formatting and linting on your commits):
   ```bash
   pre-commit install
   ```

## Where Tools Live

*   **API Endpoints:** Handled in `main.py` (soon to be refactored into routers).
*   **Processing Logic:** `scripts/pdf_utils.py`, `scripts/image_utils.py`, `scripts/excel_utils.py`, `scripts/ppt_utils.py`, etc.
*   **Frontend UI:** `static/index.html` (layout) and `static/script.js` (logic).
*   **SEO Content:** `scripts/seo_content.py` generates the static SEO landing pages.

## Running Tests

Run the full test suite before submitting a Pull Request:

```bash
DISABLE_AI=1 python -m pytest
```

If you are modifying AI layout recovery functionality, run tests without `DISABLE_AI=1` (requires >1GB RAM).

Ensure that any new features include appropriate tests in the `tests/` directory.
