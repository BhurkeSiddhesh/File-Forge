from pathlib import Path
import pytest
import pikepdf
from pdf_utils import remove_pdf_password, pdf_to_docx, extract_pdf_pages

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

def test_extract_pdf_pages(multi_page_pdf, tmp_path):
    """Test extracting selected pages from a PDF."""
    output_path_str = extract_pdf_pages(str(multi_page_pdf), str(tmp_path), "1,3-4")
    output_path = Path(output_path_str)

    assert output_path.exists()
    assert output_path.name == "multi_sample_extracted.pdf"

    with pikepdf.open(output_path) as pdf:
        assert len(pdf.pages) == 3
