from pathlib import Path
import pytest
import pikepdf
from scripts.pdf_utils import remove_pdf_password, pdf_to_docx, extract_pdf_pages, compress_pdf, _parse_page_selection

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


def test_remove_pdf_password_wrong_password(locked_pdf, tmp_path):
    """Wrong password raises an error."""
    with pytest.raises(Exception):
        remove_pdf_password(str(locked_pdf["path"]), "wrong_password", str(tmp_path))


def test_pdf_to_docx_with_password(locked_pdf, tmp_path):
    """Converting a password-protected PDF works when the correct password is supplied."""
    output_path_str = pdf_to_docx(str(locked_pdf["path"]), str(tmp_path), password=locked_pdf["password"])
    output_path = Path(output_path_str)
    assert output_path.exists()
    assert output_path.suffix == ".docx"


def test_pdf_to_docx_encrypted_no_password(locked_pdf, tmp_path):
    """Converting an encrypted PDF without a password raises ValueError."""
    with pytest.raises(ValueError, match="password"):
        pdf_to_docx(str(locked_pdf["path"]), str(tmp_path))


# ---------------------------------------------------------------------------
# _parse_page_selection tests
# ---------------------------------------------------------------------------

def test_parse_page_selection_single_page():
    """Single page number returns correct zero-based index."""
    assert _parse_page_selection("1", 5) == [0]


def test_parse_page_selection_multiple_pages():
    """Comma-separated pages return correct zero-based indices in order."""
    assert _parse_page_selection("1,3,5", 5) == [0, 2, 4]


def test_parse_page_selection_range():
    """Hyphen range returns all pages in range."""
    assert _parse_page_selection("2-4", 5) == [1, 2, 3]


def test_parse_page_selection_mixed():
    """Mixed single pages and ranges return correct indices."""
    assert _parse_page_selection("1,3-4", 4) == [0, 2, 3]


def test_parse_page_selection_all():
    """'all' keyword returns every page index."""
    assert _parse_page_selection("all", 4) == [0, 1, 2, 3]


def test_parse_page_selection_deduplication():
    """Duplicate page numbers appear only once in the result."""
    result = _parse_page_selection("1,1,2", 5)
    assert result == [0, 1]


def test_parse_page_selection_none_raises():
    """None input raises ValueError."""
    with pytest.raises(ValueError):
        _parse_page_selection(None, 5)


def test_parse_page_selection_empty_string_raises():
    """Empty string raises ValueError."""
    with pytest.raises(ValueError):
        _parse_page_selection("", 5)


def test_parse_page_selection_out_of_bounds_raises():
    """Page number beyond document length raises ValueError."""
    with pytest.raises(ValueError, match="exceeds"):
        _parse_page_selection("10", 5)


def test_parse_page_selection_zero_page_raises():
    """Page number 0 is invalid (pages are 1-based)."""
    with pytest.raises(ValueError):
        _parse_page_selection("0", 5)


def test_parse_page_selection_inverted_range_raises():
    """Range where start > end raises ValueError."""
    with pytest.raises(ValueError):
        _parse_page_selection("5-2", 5)


def test_parse_page_selection_non_numeric_raises():
    """Non-numeric page token raises ValueError."""
    with pytest.raises(ValueError):
        _parse_page_selection("abc", 5)


def test_parse_page_selection_whitespace_trimmed():
    """Leading/trailing whitespace around tokens is handled gracefully."""
    assert _parse_page_selection(" 1 , 3 ", 5) == [0, 2]


# ---------------------------------------------------------------------------
# compress_pdf tests
# ---------------------------------------------------------------------------

def test_compress_pdf_returns_dict_keys(sample_pdf, tmp_path):
    """compress_pdf returns a dict with the expected keys."""
    result = compress_pdf(str(sample_pdf), str(tmp_path), level='low')
    assert "output_path" in result
    assert "original_size" in result
    assert "compressed_size" in result
    assert "reduction_pct" in result


def test_compress_pdf_output_file_exists(sample_pdf, tmp_path):
    """compress_pdf creates an output file."""
    result = compress_pdf(str(sample_pdf), str(tmp_path), level='low')
    assert Path(result["output_path"]).exists()


def test_compress_pdf_output_is_valid_pdf(sample_pdf, tmp_path):
    """Output of compress_pdf is a valid, openable PDF."""
    result = compress_pdf(str(sample_pdf), str(tmp_path), level='low')
    with pikepdf.open(result["output_path"]) as pdf:
        assert len(pdf.pages) > 0


def test_compress_pdf_medium_level(sample_pdf, tmp_path):
    """compress_pdf works with level='medium'."""
    result = compress_pdf(str(sample_pdf), str(tmp_path), level='medium')
    assert Path(result["output_path"]).exists()


def test_compress_pdf_high_level(sample_pdf, tmp_path):
    """compress_pdf works with level='high'."""
    result = compress_pdf(str(sample_pdf), str(tmp_path), level='high')
    assert Path(result["output_path"]).exists()


def test_compress_pdf_with_password(locked_pdf, tmp_path):
    """compress_pdf decrypts and compresses a password-protected PDF."""
    result = compress_pdf(str(locked_pdf["path"]), str(tmp_path), level='low', password=locked_pdf["password"])
    assert Path(result["output_path"]).exists()


def test_compress_pdf_encrypted_no_password_raises(locked_pdf, tmp_path):
    """compress_pdf without password for encrypted PDF raises ValueError."""
    with pytest.raises(ValueError, match="password"):
        compress_pdf(str(locked_pdf["path"]), str(tmp_path))
