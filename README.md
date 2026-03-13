# File Forge

File Forge is a web-based tool for manipulating PDF files. It currently supports removing passwords from PDFs and converting PDFs to Word documents.

## Features

- **Remove Password**: Unlock password-protected PDF files.
- **Convert to Word**: Convert PDF files to DOCX format.
- **Modern UI**: Clean and responsive user interface.
- **API**: RESTful API built with FastAPI.

## Prerequisites

- Python 3.10+
- pip

## Installation

1. Clone the repository (if applicable).
2. Install the required dependencies:

   ```bash
   pip install -r requirements.txt
   ```

## Running the Application

To start the server, run:

```bash
python main.py
```

The application will be available at `http://127.0.0.1:8001`.

## Running Tests

This project uses `pytest` for testing. To run the tests, execute:

```bash
python -m pytest
```

### Test Structure

- `tests/conftest.py`: Contains test fixtures, including generation of mock PDF files (locked and unlocked).
- `tests/test_pdf_utils.py`: Unit tests for the core PDF processing logic.
- `tests/test_main.py`: Integration tests for the FastAPI endpoints.

The tests automatically create temporary files for testing and clean them up afterwards, ensuring no test data is left behind.

## Deployment

### Deploy to Render

1. **Connect GitHub**: Log in to [Render](https://render.com/) and connect your GitHub repository.
2. **Select Blueprint**: Render will automatically detect the `render.yaml` file.
3. **Deploy**: Follow the prompts to create the "File Forge" web service.

> [!IMPORTANT]
> Because this app uses **PaddleOCR** for high-quality PDF conversion, it requires at least **1GB or 2GB of RAM** (the Render **Starter** plan or higher). The Free Tier (512MB) may crash during AI model initialization.

## Project Structure

- `main.py`: The FastAPI application entry point.
- `scripts/`:
    - `pdf_utils.py`: Utility functions for PDF processing.
    - `image_utils.py`: HEIC conversion and image processing.
    - `utils.py`: Common shared utilities.
- `static/`: Contains static assets (HTML, CSS, JS).
- `uploads/`: Temporary storage for raw uploads.
- `outputs/`: Storage for processed files.
- `tests/`: Comprehensive test suite.
- `Dockerfile`: Configuration for containerized deployment.
- `render.yaml`: Configuration for one-click Render deployment.

![CodeRabbit Pull Request Reviews](https://img.shields.io/coderabbit/prs/github/BhurkeSiddhesh/File-Forge?utm_source=oss&utm_medium=github&utm_campaign=BhurkeSiddhesh%2FFile-Forge&labelColor=171717&color=FF570A&link=https%3A%2F%2Fcoderabbit.ai&label=CodeRabbit+Reviews)
