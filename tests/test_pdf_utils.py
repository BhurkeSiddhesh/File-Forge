import pytest
from pathlib import Path
from pdf_utils import remove_pdf_password, pdf_to_docx
import pikepdf

def test_remove_pdf_password(locked_pdf, tmp_path):
    """Test removing password from a PDF."""
    input_path = locked_pdf["path"]
    password = locked_pdf["password"]

    # Use tmp_path as the output directory
    output_path_str = remove_pdf_password(str(input_path), password, str(tmp_path))
    output_path = Path(output_path_str)

    assert output_path.exists()
    assert output_path.name == "locked_unlocked.pdf"

    # Verify the file can be opened without password
    with pikepdf.open(output_path) as pdf:
        assert len(pdf.pages) > 0

def test_pdf_to_docx(sample_pdf, tmp_path):
    """Test converting PDF to DOCX."""
    output_path_str = pdf_to_docx(str(sample_pdf), str(tmp_path))
    output_path = Path(output_path_str)

    assert output_path.exists()
    assert output_path.suffix == ".docx"
    assert output_path.stem == sample_pdf.stem
