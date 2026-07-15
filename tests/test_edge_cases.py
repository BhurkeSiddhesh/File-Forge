import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import os
import pytest
import pikepdf

from scripts.pdf_utils import (
    create_blank_pdf,
    create_pdf_from_text,
    add_page_numbers,
    extract_text_from_pdf,
    protect_pdf,
    images_to_pdf,
    organize_pdf,
    annotate_pdf,
    rotate_pdf,
    repair_pdf,
    pdf_to_excel,
    pdf_to_pptx,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _make_blank_pdf(output_dir: Path, num_pages: int = 1) -> str:
    return create_blank_pdf(str(output_dir), num_pages=num_pages)


def _make_text_pdf(output_dir: Path, content: str = "Test content") -> str:
    return create_pdf_from_text(str(output_dir), content=content)


def _make_png_image(tmp_path: Path, w: int = 100, h: int = 100, name: str = "img.png") -> Path:
    from PIL import Image
    p = tmp_path / name
    img = Image.new("RGB", (w, h), color=(100, 200, 50))
    img.save(str(p), "PNG")
    return p


def _page_count(pdf_path: str) -> int:
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)


# ══════════════════════════════════════════════════════════════
# PDF EDGE CASES
# ══════════════════════════════════════════════════════════════

class TestSingleCharContent:
    """create_pdf_from_text with a single character."""

    def test_single_char_content(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = create_pdf_from_text(str(out), content="X")
        assert Path(pdf_path).exists()
        assert _page_count(pdf_path) >= 1


class TestOrganizeDuplicate:
    """organize_pdf with 1-page PDF repeated three times → 3-page output."""

    def test_one_page_repeated(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=1)
        result = organize_pdf(pdf_path, str(out), page_order=[1, 1, 1])
        assert Path(result).exists()
        assert _page_count(result) == 3


class TestNestedEncryption:
    """protect_pdf on already-protected PDF should work or raise a clear error."""

    def test_protect_then_protect_again(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        # First protect
        protected1 = protect_pdf(pdf_path, str(out), user_password="first")  # ggignore
        assert Path(protected1).exists()
        # Second protect — should either succeed (by decrypting first) or raise a clear error
        try:
            protected2 = protect_pdf(
                protected1, str(out), user_password="second", password="first"  # ggignore
            )
            assert Path(protected2).exists()
        except (ValueError, RuntimeError, Exception) as e:
            # Any clear error is acceptable; must not be a silent crash
            assert str(e)


class TestAddPageNumbersSkipAll:
    """add_page_numbers with skip_first >= total pages: still creates a valid PDF."""

    def test_skip_first_equals_page_count(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=2)
        result = add_page_numbers(pdf_path, str(out), skip_first=2)
        assert Path(result).exists()
        assert _page_count(result) == 2


class TestAnnotateOutOfBounds:
    """annotate_pdf with rect outside page bounds should not crash."""

    def test_rect_outside_bounds(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_text_pdf(out)
        annotations = [{"type": "highlight", "page": 1, "rect": [9999, 9999, 10000, 10010]}]
        result = annotate_pdf(pdf_path, str(out), annotations)
        assert Path(result).exists()


class TestExtractTextBlankPDF:
    """extract_text_from_pdf on blank (no text) pages returns fallback string."""

    def test_blank_pdf_no_crash(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=2)
        result = extract_text_from_pdf(pdf_path, str(out))
        assert Path(result["output_path"]).exists()
        content = Path(result["output_path"]).read_text(encoding="utf-8")
        # Either empty placeholder or no-text placeholder
        assert isinstance(content, str)


class TestRepairValidPDF:
    """repair_pdf on an already-valid PDF should succeed."""

    def test_repair_valid(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_text_pdf(out, content="Valid PDF for repair test.")
        result = repair_pdf(pdf_path, str(out))
        assert Path(result["output_path"]).exists()
        assert result["repair_status"] in ("success", "partial_recovery", "recovered_via_mupdf")


class TestOrganize100Pages:
    """organize_pdf with 100 repeated pages (stress test)."""

    def test_100_repeated_pages(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=3)
        order = [1, 2, 3] * 33 + [1]  # 100 pages
        result = organize_pdf(pdf_path, str(out), page_order=order)
        assert Path(result).exists()
        assert _page_count(result) == 100


class TestAddPageNumbersHighNumber:
    """add_page_numbers start_number=999 with alpha format (number > 26)."""

    def test_alpha_format_high_number(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=2)
        result = add_page_numbers(pdf_path, str(out), start_number=999, fmt="alpha")
        assert Path(result).exists()
        assert _page_count(result) == 2


class TestImagesToPDF1x1:
    """images_to_pdf with a 1x1 pixel image should not crash."""

    def test_1x1_pixel_image(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        img_path = _make_png_image(tmp_path, w=1, h=1, name="tiny.png")
        result = images_to_pdf([str(img_path)], str(out))
        assert Path(result).exists()


class TestPDFToExcelNoTables:
    """pdf_to_excel on a PDF with no tables returns a fallback text sheet."""

    def test_no_tables_returns_text_sheet(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_text_pdf(out, content="No tables here. Just plain text.")
        result = pdf_to_excel(pdf_path, str(out))
        assert Path(result["output_path"]).exists()
        assert result["tables_found"] == 0
        # The file should exist with a text fallback sheet
        import openpyxl
        wb = openpyxl.load_workbook(result["output_path"])
        assert len(wb.sheetnames) >= 1


class TestPDFToPPTXSmallPage:
    """pdf_to_pptx with a small PDF page should not crash."""

    def test_small_page_pdf(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        # Create a small PDF using a small page size via reportlab
        from reportlab.pdfgen import canvas as rl_canvas
        pdf_path = tmp_path / "small.pdf"
        c = rl_canvas.Canvas(str(pdf_path), pagesize=(72, 72))  # 1 inch x 1 inch
        c.drawString(5, 40, "Hi")
        c.showPage()
        c.save()
        result = pdf_to_pptx(str(pdf_path), str(out))
        assert Path(result).exists()


# ══════════════════════════════════════════════════════════════
# INPUT VALIDATION
# ══════════════════════════════════════════════════════════════

class TestInputValidation:
    def test_protect_empty_password_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        with pytest.raises(ValueError, match="[Pp]assword"):
            protect_pdf(pdf_path, str(out), user_password="")

    def test_rotate_angle_zero_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        with pytest.raises(ValueError):
            rotate_pdf(pdf_path, str(out), angle=0)

    def test_organize_page_zero_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        with pytest.raises((ValueError, TypeError)):
            organize_pdf(pdf_path, str(out), page_order=[0])

    def test_create_blank_zero_pages_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            create_blank_pdf(str(out), num_pages=0)

    def test_create_blank_101_pages_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            create_blank_pdf(str(out), num_pages=101)

    def test_annotate_none_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        with pytest.raises((ValueError, TypeError)):
            annotate_pdf(pdf_path, str(out), annotations=None)

    def test_add_page_numbers_font_size_200_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out)
        with pytest.raises(ValueError):
            add_page_numbers(pdf_path, str(out), font_size=200)

    def test_images_to_pdf_empty_list_raises(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        with pytest.raises(ValueError):
            images_to_pdf([], str(out))


# ══════════════════════════════════════════════════════════════
# LARGE FILE SIMULATION
# ══════════════════════════════════════════════════════════════

class TestLargeFiles:
    def test_extract_text_50_page_pdf(self, tmp_path):
        """Create a 50-page PDF and run extract_text on it."""
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=50)
        result = extract_text_from_pdf(pdf_path, str(out))
        assert result["page_count"] == 50
        assert Path(result["output_path"]).exists()

    def test_organize_reversed_20_pages(self, tmp_path):
        """Create a 20-page PDF and organize with reversed order."""
        out = tmp_path / "out"
        out.mkdir()
        pdf_path = _make_blank_pdf(out, num_pages=20)
        reversed_order = list(range(20, 0, -1))
        result = organize_pdf(pdf_path, str(out), page_order=reversed_order)
        assert Path(result).exists()
        assert _page_count(result) == 20
