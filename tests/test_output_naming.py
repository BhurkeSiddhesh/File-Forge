"""
Tests for the download filename convention.

Uploaded files are saved as "<uuid4>_<original_filename>" (see main.py) to avoid
collisions between concurrent uploads. Every conversion function derives its
output filename from that temp file, so it must strip the UUID prefix back off
and brand the result as "<original name>_forgefiles.org.<ext>" instead of
leaking the UUID (or dropping the branding) into the file the user downloads.
"""
from pathlib import Path
import uuid

import pytest

from scripts.utils import original_stem, branded_filename
from scripts.pdf_utils import compress_pdf, pdf_to_docx
from scripts.image_utils import heic_to_jpeg
from scripts.excel_utils import csv_to_xlsx


def _as_uploaded_temp_path(tmp_path: Path, original_name: str) -> Path:
    """Mirror main.py's `f"{uuid.uuid4()}_{safe_filename}"` temp-upload naming."""
    return tmp_path / f"{uuid.uuid4()}_{original_name}"


# ──────────────────────────────────────────────────────────────
# Unit tests: original_stem / branded_filename
# ──────────────────────────────────────────────────────────────

def test_original_stem_strips_uuid_prefix():
    uuid_prefixed = Path(f"{uuid.uuid4()}_MyReport.pdf")
    assert original_stem(uuid_prefixed) == "MyReport"


def test_original_stem_preserves_case_and_spaces():
    uuid_prefixed = Path(f"{uuid.uuid4()}_Quarterly Report Final.pdf")
    assert original_stem(uuid_prefixed) == "Quarterly Report Final"


def test_original_stem_leaves_non_uuid_names_untouched():
    # No UUID prefix (e.g. a path not produced by the upload flow) should pass through.
    assert original_stem(Path("plainname.pdf")) == "plainname"


def test_original_stem_does_not_strip_a_look_alike_prefix():
    # Only an exact UUID4-shaped prefix should be stripped, not any underscore-separated text.
    assert original_stem(Path("not-a-uuid_report.pdf")) == "not-a-uuid_report"


def test_branded_filename_format():
    uuid_prefixed = Path(f"{uuid.uuid4()}_MyReport.pdf")
    assert branded_filename(uuid_prefixed, "pdf") == "MyReport_forgefiles.org.pdf"


def test_branded_filename_strips_leading_dot_from_ext():
    uuid_prefixed = Path(f"{uuid.uuid4()}_MyReport.pdf")
    assert branded_filename(uuid_prefixed, ".pdf") == "MyReport_forgefiles.org.pdf"


# ──────────────────────────────────────────────────────────────
# Integration tests: real conversion functions given a real
# upload-style (UUID-prefixed) temp path
# ──────────────────────────────────────────────────────────────

def test_compress_pdf_output_name_is_branded(sample_pdf, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    temp_upload = _as_uploaded_temp_path(tmp_path, "Sample.pdf")
    temp_upload.write_bytes(Path(sample_pdf).read_bytes())

    result = compress_pdf(str(temp_upload), str(out_dir))
    output_name = Path(result["output_path"]).name

    assert output_name == "Sample_forgefiles.org.pdf"


def test_pdf_to_docx_output_name_is_branded(sample_pdf, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    temp_upload = _as_uploaded_temp_path(tmp_path, "Contract Draft.pdf")
    temp_upload.write_bytes(Path(sample_pdf).read_bytes())

    output_path = pdf_to_docx(str(temp_upload), str(out_dir))

    assert Path(output_path).name == "Contract Draft_forgefiles.org.docx"


def test_heic_to_jpeg_output_name_is_branded(sample_heic, tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    temp_upload = _as_uploaded_temp_path(tmp_path, "Vacation Photo.heic")
    temp_upload.write_bytes(Path(sample_heic).read_bytes())

    output_path = heic_to_jpeg(str(temp_upload), str(out_dir))

    assert Path(output_path).name == "Vacation Photo_forgefiles.org.jpg"


def test_csv_to_xlsx_output_name_is_branded(tmp_path):
    out_dir = tmp_path / "out"
    out_dir.mkdir()
    temp_upload = _as_uploaded_temp_path(tmp_path, "Budget.csv")
    temp_upload.write_text("a,b,c\n1,2,3\n")

    output_path = csv_to_xlsx(str(temp_upload), str(out_dir))

    assert Path(output_path).name == "Budget_forgefiles.org.xlsx"


# ──────────────────────────────────────────────────────────────
# End-to-end: the actual API response filename
# ──────────────────────────────────────────────────────────────

def test_api_compress_pdf_returns_branded_filename(auth_client, sample_pdf):
    with open(sample_pdf, "rb") as f:
        response = auth_client.post(
            "/api/pdf/compress",
            files={"file": ("Annual Report.pdf", f, "application/pdf")},
        )

    assert response.status_code == 200
    data = response.json()
    assert data["filename"] == "Annual Report_forgefiles.org.pdf"
