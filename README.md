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

## Project Structure

- `main.py`: The FastAPI application entry point.
- `pdf_utils.py`: Utility functions for PDF processing using `pikepdf` and `pdf2docx`.
- `static/`: Contains static assets (HTML, CSS, JS).
- `uploads/`: Directory where uploaded files are temporarily stored (created automatically).
- `outputs/`: Directory where processed files are saved (created automatically).
- `tests/`: Contains the test suite.
