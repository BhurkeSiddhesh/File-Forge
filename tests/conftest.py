import pytest
from pathlib import Path
from reportlab.pdfgen import canvas
import pikepdf

@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    """Creates a simple PDF file for testing."""
    # Create a temporary directory for the session
    d = tmp_path_factory.mktemp("data")
    file_path = d / "sample.pdf"

    # Generate PDF using ReportLab
    c = canvas.Canvas(str(file_path))
    c.drawString(100, 750, "Hello, this is a test PDF.")
    c.save()

    return file_path

@pytest.fixture(scope="session")
def locked_pdf(tmp_path_factory, sample_pdf):
    """Creates a password-protected PDF file."""
    d = tmp_path_factory.mktemp("locked_data")
    file_path = d / "locked.pdf"
    password = "secret_password"

    with pikepdf.open(sample_pdf) as pdf:
        # Encrypt the PDF
        pdf.save(
            file_path,
            encryption=pikepdf.Encryption(
                user=password,
                owner=password
            )
        )

    return {"path": file_path, "password": password}
