"""
Comprehensive tests for all 12 new features (#53–#64).
Runs standalone without the full app (no docxcompose dependency).
"""
import json
import sys
import tempfile
from io import BytesIO
from pathlib import Path

import pikepdf
import pytest
from PIL import Image as PILImage
from reportlab.pdfgen import canvas

sys.path.insert(0, str(Path(__file__).parent.parent))

_TEST_PW = "test-pdf-pw"  # ggignore
_TEST_OWNER_PW = "test-pdf-owner-pw"  # ggignore

from scripts.pdf_utils import (
    protect_pdf,
    images_to_pdf,
    word_to_pdf,
    pdf_to_excel,
    pdf_to_pptx,
    extract_text_from_pdf,
    organize_pdf,
    add_page_numbers,
    repair_pdf,
    create_pdf_from_text,
    create_blank_pdf,
    annotate_pdf,
    edit_pdf_metadata,
    get_pdf_metadata,
)


# ──────────────────────────────────────────────
# Shared Fixtures
# ──────────────────────────────────────────────


@pytest.fixture
def simple_pdf(tmp_path):
    p = tmp_path / "simple.pdf"
    c = canvas.Canvas(str(p))
    c.drawString(100, 750, "Hello world")
    c.save()
    return p


@pytest.fixture
def multi_page_pdf(tmp_path):
    p = tmp_path / "multi.pdf"
    c = canvas.Canvas(str(p))
    for i in range(1, 5):
        c.drawString(100, 750, f"Page {i} content")
        c.showPage()
    c.save()
    return p


@pytest.fixture
def locked_pdf(tmp_path, simple_pdf):
    p = tmp_path / "locked.pdf"
    pw = "secret"
    with pikepdf.open(simple_pdf) as pdf:
        pdf.save(p, encryption=pikepdf.Encryption(user=pw, owner=pw))
    return {"path": p, "password": pw}


@pytest.fixture
def sample_image(tmp_path):
    p = tmp_path / "img.png"
    img = PILImage.new("RGB", (200, 150), color=(100, 149, 237))
    img.save(p, "PNG")
    return p


@pytest.fixture
def sample_jpeg(tmp_path):
    p = tmp_path / "img.jpg"
    img = PILImage.new("RGB", (300, 200), color=(200, 100, 50))
    img.save(p, "JPEG")
    return p


@pytest.fixture
def sample_docx(tmp_path):
    """Create a minimal DOCX file for word_to_pdf testing."""
    try:
        from docx import Document
        p = tmp_path / "sample.docx"
        doc = Document()
        doc.add_paragraph("Hello, this is a test document.")
        doc.save(str(p))
        return p
    except ImportError:
        pytest.skip("python-docx not available")


@pytest.fixture
def pdf_with_table(tmp_path):
    """Create a PDF containing tabular data using PyMuPDF."""
    import fitz
    p = tmp_path / "table.pdf"
    doc = fitz.open()
    page = doc.new_page()
    # Draw a simple table structure
    shape = page.new_shape()
    # Draw grid lines
    for row in range(4):
        y = 700 - row * 40
        shape.draw_line(fitz.Point(50, y), fitz.Point(350, y))
    for col in range(4):
        x = 50 + col * 100
        shape.draw_line(fitz.Point(x, 700), fitz.Point(x, 580))
    shape.finish(color=(0, 0, 0))
    shape.commit()
    # Add text
    for row in range(3):
        for col in range(3):
            page.insert_text(
                fitz.Point(55 + col * 100, 690 - row * 40),
                f"R{row}C{col}",
                fontsize=10,
            )
    doc.save(str(p))
    doc.close()
    return p


# ──────────────────────────────────────────────
# Feature #53: Protect PDF
# ──────────────────────────────────────────────

class TestProtectPDF:
    def test_protect_creates_file(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(str(simple_pdf), str(out), user_password=_TEST_PW)
        assert Path(result).exists()
        assert "_forgefiles.org.pdf" in result

    def test_protected_pdf_requires_password(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(str(simple_pdf), str(out), user_password=_TEST_PW)
        with pytest.raises(pikepdf.PasswordError):
            pikepdf.open(result)

    def test_protected_pdf_opens_with_correct_password(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(str(simple_pdf), str(out), user_password=_TEST_PW)
        with pikepdf.open(result, password=_TEST_PW) as pdf:
            assert len(pdf.pages) >= 1

    def test_protect_empty_password_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="password"):
            protect_pdf(str(simple_pdf), str(out), user_password="")

    def test_protect_already_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(
            str(locked_pdf["path"]), str(out),
            user_password=_TEST_PW,
            password=locked_pdf["password"],
        )
        assert Path(result).exists()

    def test_protect_preserves_page_count(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(str(multi_page_pdf), str(out), user_password=_TEST_PW)
        with pikepdf.open(result, password=_TEST_PW) as pdf:
            assert len(pdf.pages) == 4

    def test_protect_with_owner_password(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = protect_pdf(str(simple_pdf), str(out), user_password=_TEST_PW, owner_password=_TEST_OWNER_PW)
        with pikepdf.open(result, password=_TEST_PW) as pdf:
            assert len(pdf.pages) >= 1


# ──────────────────────────────────────────────
# Feature #54: Image to PDF
# ──────────────────────────────────────────────

class TestImagesToPDF:
    def test_single_image_creates_pdf(self, sample_image, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = images_to_pdf([str(sample_image)], str(out))
        assert Path(result).exists()
        assert result.endswith(".pdf")
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_multiple_images_multi_page(self, sample_image, sample_jpeg, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = images_to_pdf([str(sample_image), str(sample_jpeg)], str(out))
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_no_images_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            images_to_pdf([], str(out))

    def test_letter_page_size(self, sample_image, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = images_to_pdf([str(sample_image)], str(out), page_size="Letter")
        assert Path(result).exists()

    def test_auto_page_size(self, sample_image, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = images_to_pdf([str(sample_image)], str(out), page_size="auto")
        assert Path(result).exists()

    def test_fit_mode_original(self, sample_image, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = images_to_pdf([str(sample_image)], str(out), fit_mode="original")
        assert Path(result).exists()

    def test_three_images(self, sample_image, sample_jpeg, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        # Use same image three times
        result = images_to_pdf([str(sample_image), str(sample_jpeg), str(sample_image)], str(out))
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 3


# ──────────────────────────────────────────────
# Feature #55: Word to PDF
# ──────────────────────────────────────────────

class TestWordToPDF:
    def test_docx_converts_to_pdf(self, sample_docx, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = word_to_pdf(str(sample_docx), str(out))
        assert Path(result).exists()
        assert result.endswith(".pdf")
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) >= 1

    def test_invalid_extension_raises(self, tmp_path):
        fake = tmp_path / "file.xyz"
        fake.write_text("not a doc")
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="docx"):
            word_to_pdf(str(fake), str(out))

    def test_output_is_valid_pdf(self, sample_docx, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = word_to_pdf(str(sample_docx), str(out))
        # Verify it's a valid PDF by checking header
        with open(result, "rb") as f:
            header = f.read(5)
        assert header == b"%PDF-"


# ──────────────────────────────────────────────
# Feature #56: PDF to Excel
# ──────────────────────────────────────────────

class TestPDFToExcel:
    def test_creates_excel_file(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(simple_pdf), str(out))
        assert Path(result["output_path"]).exists()
        assert result["output_path"].endswith(".xlsx")

    def test_returns_tables_found_count(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(simple_pdf), str(out))
        assert "tables_found" in result
        assert isinstance(result["tables_found"], int)

    def test_pdf_with_table_extracts_data(self, pdf_with_table, tmp_path):
        import openpyxl
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(pdf_with_table), str(out))
        wb = openpyxl.load_workbook(result["output_path"])
        assert len(wb.sheetnames) >= 1

    def test_multi_page_pdf_processes_all(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(multi_page_pdf), str(out))
        assert Path(result["output_path"]).exists()

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(locked_pdf["path"]), str(out), password=locked_pdf["password"])
        assert Path(result["output_path"]).exists()

    def test_no_tables_fallback_text(self, simple_pdf, tmp_path):
        import openpyxl
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_excel(str(simple_pdf), str(out))
        wb = openpyxl.load_workbook(result["output_path"])
        # Should have at least one sheet (text fallback or table sheet)
        assert len(wb.sheetnames) >= 1


# ──────────────────────────────────────────────
# Feature #57: PDF to PowerPoint
# ──────────────────────────────────────────────

class TestPDFToPPTX:
    def test_creates_pptx_file(self, simple_pdf, tmp_path):
        from pptx import Presentation
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_pptx(str(simple_pdf), str(out))
        assert Path(result).exists()
        assert result.endswith(".pptx")

    def test_slide_count_matches_pages(self, multi_page_pdf, tmp_path):
        from pptx import Presentation
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_pptx(str(multi_page_pdf), str(out))
        prs = Presentation(result)
        assert len(prs.slides) == 4

    def test_single_page_pdf(self, simple_pdf, tmp_path):
        from pptx import Presentation
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_pptx(str(simple_pdf), str(out))
        prs = Presentation(result)
        assert len(prs.slides) == 1

    def test_invalid_dpi_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="DPI"):
            pdf_to_pptx(str(simple_pdf), str(out), dpi=500)

    def test_with_locked_pdf(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = pdf_to_pptx(str(locked_pdf["path"]), str(out), password=locked_pdf["password"])
        assert Path(result).exists()


# ──────────────────────────────────────────────
# Feature #58: Extract Text from PDF
# ──────────────────────────────────────────────

class TestExtractText:
    def test_creates_txt_file(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(simple_pdf), str(out))
        assert Path(result["output_path"]).exists()
        assert result["output_path"].endswith(".txt")

    def test_extracts_text_content(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(simple_pdf), str(out))
        text = Path(result["output_path"]).read_text(encoding="utf-8")
        assert "Hello world" in text

    def test_returns_page_count(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(multi_page_pdf), str(out))
        assert result["page_count"] == 4

    def test_preserve_layout_mode(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(simple_pdf), str(out), preserve_layout=True)
        assert Path(result["output_path"]).exists()

    def test_page_headers_in_output(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(multi_page_pdf), str(out))
        text = Path(result["output_path"]).read_text(encoding="utf-8")
        assert "--- Page 1 ---" in text

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(locked_pdf["path"]), str(out), password=locked_pdf["password"])
        assert Path(result["output_path"]).exists()

    def test_output_filename_contains_text(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = extract_text_from_pdf(str(simple_pdf), str(out))
        assert "_forgefiles.org.txt" in result["output_path"]


# ──────────────────────────────────────────────
# Feature #59: Organize PDF
# ──────────────────────────────────────────────

class TestOrganizePDF:
    def test_reorder_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(multi_page_pdf), str(out), page_order=[4, 3, 2, 1])
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 4

    def test_delete_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(multi_page_pdf), str(out), page_order=[1, 3])
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 2

    def test_duplicate_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(multi_page_pdf), str(out), page_order=[1, 1, 2])
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 3

    def test_empty_order_raises(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            organize_pdf(str(multi_page_pdf), str(out), page_order=[])

    def test_out_of_range_page_raises(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            organize_pdf(str(multi_page_pdf), str(out), page_order=[1, 99])

    def test_output_filename(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(multi_page_pdf), str(out), page_order=[1, 2])
        assert "_forgefiles.org.pdf" in result

    def test_single_page_extract(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(multi_page_pdf), str(out), page_order=[2])
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = organize_pdf(str(locked_pdf["path"]), str(out), page_order=[1], password=locked_pdf["password"])
        assert Path(result).exists()


# ──────────────────────────────────────────────
# Feature #60: Add Page Numbers
# ──────────────────────────────────────────────

class TestAddPageNumbers:
    def test_creates_numbered_pdf(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out))
        assert Path(result).exists()
        assert "_forgefiles.org.pdf" in result

    def test_page_count_preserved(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out))
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 4

    def test_all_positions(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        positions = ["bottom-center", "bottom-left", "bottom-right",
                     "top-center", "top-left", "top-right"]
        for pos in positions:
            result = add_page_numbers(str(simple_pdf), str(out), position=pos)
            assert Path(result).exists(), f"Failed for position: {pos}"

    def test_invalid_position_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="position"):
            add_page_numbers(str(simple_pdf), str(out), position="middle")

    def test_roman_format(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out), fmt="roman")
        assert Path(result).exists()

    def test_alpha_format(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out), fmt="alpha")
        assert Path(result).exists()

    def test_skip_first_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out), skip_first=1)
        assert Path(result).exists()

    def test_custom_start_number(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(multi_page_pdf), str(out), start_number=5)
        assert Path(result).exists()

    def test_invalid_format_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="fmt"):
            add_page_numbers(str(simple_pdf), str(out), fmt="unknown")

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = add_page_numbers(str(locked_pdf["path"]), str(out), password=locked_pdf["password"])
        assert Path(result).exists()


# ──────────────────────────────────────────────
# Feature #61: Repair PDF
# ──────────────────────────────────────────────

class TestRepairPDF:
    def test_repair_valid_pdf(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = repair_pdf(str(simple_pdf), str(out))
        assert Path(result["output_path"]).exists()
        assert result["repair_status"] in ("success", "partial_recovery", "recovered_via_mupdf")

    def test_repair_output_is_valid_pdf(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = repair_pdf(str(simple_pdf), str(out))
        with pikepdf.open(result["output_path"]) as pdf:
            assert len(pdf.pages) >= 1

    def test_repair_output_filename(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = repair_pdf(str(simple_pdf), str(out))
        assert "_forgefiles.org.pdf" in result["output_path"]

    def test_repair_preserves_pages(self, multi_page_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = repair_pdf(str(multi_page_pdf), str(out))
        with pikepdf.open(result["output_path"]) as pdf:
            assert len(pdf.pages) == 4

    def test_repair_truncated_pdf(self, tmp_path):
        """Test repair on a partially truncated PDF."""
        out = tmp_path / "out"
        out.mkdir()

        # Create a valid PDF, then truncate it
        good_pdf = tmp_path / "good.pdf"
        c = canvas.Canvas(str(good_pdf))
        c.drawString(100, 750, "test")
        c.save()
        good_bytes = good_pdf.read_bytes()

        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_bytes(good_bytes[: len(good_bytes) // 2])

        try:
            result = repair_pdf(str(bad_pdf), str(out))
            assert "output_path" in result
        except RuntimeError:
            # Expected for severely corrupted files
            pass


# ──────────────────────────────────────────────
# Feature #62: Create PDF from Scratch
# ──────────────────────────────────────────────

class TestCreatePDF:
    def test_create_from_text(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_pdf_from_text(str(out), "Hello world\nSecond line")
        assert Path(result).exists()
        assert result.endswith(".pdf")
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) >= 1

    def test_empty_content_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="empty"):
            create_pdf_from_text(str(out), "   ")

    def test_custom_title(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_pdf_from_text(str(out), "Content", title="My Report")
        assert "My_Report" in result

    def test_letter_page_size(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_pdf_from_text(str(out), "Content", page_size="Letter")
        assert Path(result).exists()

    def test_large_text_creates_multiple_pages(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        content = "\n".join([f"Line {i}: " + "A" * 80 for i in range(200)])
        result = create_pdf_from_text(str(out), content)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) >= 2

    def test_create_blank_pdf(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_blank_pdf(str(out), num_pages=3)
        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 3

    def test_create_blank_single_page(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_blank_pdf(str(out), num_pages=1)
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1

    def test_blank_pdf_invalid_pages_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            create_blank_pdf(str(out), num_pages=0)
        with pytest.raises(ValueError):
            create_blank_pdf(str(out), num_pages=101)

    def test_blank_pdf_letter_size(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_blank_pdf(str(out), num_pages=2, page_size="Letter")
        assert Path(result).exists()

    def test_special_chars_in_content(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = create_pdf_from_text(str(out), "Hello <world> & 'more'")
        assert Path(result).exists()


# ──────────────────────────────────────────────
# Feature #63: Annotate PDF
# ──────────────────────────────────────────────

class TestAnnotatePDF:
    def _make_annot(self, ann_type, page=1, rect=None, content="test"):
        return {
            "type": ann_type,
            "page": page,
            "rect": rect or [50, 700, 300, 730],
            "content": content,
        }

    def test_highlight_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        anns = [self._make_annot("highlight")]
        result = annotate_pdf(str(simple_pdf), str(out), anns)
        assert Path(result).exists()
        assert "_forgefiles.org.pdf" in result

    def test_underline_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [self._make_annot("underline")])
        assert Path(result).exists()

    def test_strikeout_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [self._make_annot("strikeout")])
        assert Path(result).exists()

    def test_note_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [self._make_annot("note", content="Review this")])
        assert Path(result).exists()

    def test_text_box_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [self._make_annot("text", content="Added text")])
        assert Path(result).exists()

    def test_redact_annotation(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [self._make_annot("redact")])
        assert Path(result).exists()

    def test_multiple_annotations(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        anns = [
            self._make_annot("highlight", rect=[50, 700, 200, 720]),
            self._make_annot("underline", rect=[50, 670, 200, 690]),
            self._make_annot("note", content="Note here"),
        ]
        result = annotate_pdf(str(simple_pdf), str(out), anns)
        assert Path(result).exists()

    def test_invalid_type_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="annotation type"):
            annotate_pdf(str(simple_pdf), str(out), [self._make_annot("magic")])

    def test_out_of_range_page_raises(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError, match="out of range"):
            annotate_pdf(str(simple_pdf), str(out), [self._make_annot("highlight", page=99)])

    def test_empty_annotations_list(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = annotate_pdf(str(simple_pdf), str(out), [])
        assert Path(result).exists()

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        anns = [self._make_annot("highlight")]
        result = annotate_pdf(str(locked_pdf["path"]), str(out), anns, password=locked_pdf["password"])
        assert Path(result).exists()

    def test_custom_highlight_color(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        ann = {"type": "highlight", "page": 1, "rect": [50, 700, 200, 720], "color": [0, 1, 0]}
        result = annotate_pdf(str(simple_pdf), str(out), [ann])
        assert Path(result).exists()


# ──────────────────────────────────────────────
# Feature #64: PDF Metadata Editor
# ──────────────────────────────────────────────

class TestPDFMetadata:
    def test_edit_title(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(str(simple_pdf), str(out), title="My Title")
        assert Path(result).exists()

    def test_edit_author(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(str(simple_pdf), str(out), author="John Doe")
        with pikepdf.open(result) as pdf:
            assert str(pdf.docinfo.get("/Author", "")) == "John Doe"

    def test_edit_multiple_fields(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(
            str(simple_pdf), str(out),
            title="Test", author="Author", subject="Subject", keywords="a,b,c"
        )
        with pikepdf.open(result) as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "Test"
            assert str(pdf.docinfo.get("/Author", "")) == "Author"

    def test_read_metadata(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        # Write metadata first
        edited = edit_pdf_metadata(str(simple_pdf), str(out), title="ReadTest", author="TestAuthor")
        meta = get_pdf_metadata(edited)
        assert meta["title"] == "ReadTest"
        assert meta["author"] == "TestAuthor"
        assert "page_count" in meta
        assert meta["page_count"] >= 1

    def test_clear_all_metadata(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        # First set some metadata
        edited = edit_pdf_metadata(str(simple_pdf), str(out), title="ToRemove", author="ToRemove")
        # Then clear all
        cleared = edit_pdf_metadata(edited, str(out), clear_all=True)
        assert Path(cleared).exists()

    def test_none_fields_keep_existing(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(str(simple_pdf), str(out), title="Keep", author=None)
        with pikepdf.open(result) as pdf:
            assert str(pdf.docinfo.get("/Title", "")) == "Keep"

    def test_locked_pdf_with_password(self, locked_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(
            str(locked_pdf["path"]), str(out),
            title="Locked Title",
            password=locked_pdf["password"]
        )
        assert Path(result).exists()

    def test_output_filename(self, simple_pdf, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        result = edit_pdf_metadata(str(simple_pdf), str(out), title="Test")
        assert "_forgefiles.org.pdf" in result

    def test_get_metadata_page_count(self, multi_page_pdf, tmp_path):
        meta = get_pdf_metadata(str(multi_page_pdf))
        assert meta["page_count"] == 4

    def test_get_metadata_returns_dict(self, simple_pdf, tmp_path):
        meta = get_pdf_metadata(str(simple_pdf))
        expected_keys = {"title", "author", "subject", "keywords", "creator", "producer", "page_count"}
        assert expected_keys.issubset(set(meta.keys()))
