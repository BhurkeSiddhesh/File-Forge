import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

_TEST_PW = "test-pdf-pw"  # ggignore

import io
import os
import pytest
import pikepdf

from scripts.pdf_utils import (
    create_blank_pdf,
    create_pdf_from_text,
    add_page_numbers,
    extract_text_from_pdf,
    compress_pdf,
    protect_pdf,
    images_to_pdf,
    organize_pdf,
    annotate_pdf,
    edit_pdf_metadata,
    rotate_pdf,
    word_to_pdf,
)


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _make_png_image(tmp_path: Path, w: int = 100, h: int = 100, name: str = "img.png") -> Path:
    from PIL import Image
    p = tmp_path / name
    img = Image.new("RGB", (w, h), color=(100, 200, 50))
    img.save(str(p), "PNG")
    return p


def _make_docx(tmp_path: Path) -> Path:
    from docx import Document
    doc = Document()
    doc.add_paragraph("Workflow test DOCX content.")
    p = tmp_path / "workflow.docx"
    doc.save(str(p))
    return p


def _page_count(pdf_path: str) -> int:
    with pikepdf.open(pdf_path) as pdf:
        return len(pdf.pages)


def _page_count_protected(pdf_path: str, password: str) -> int:
    with pikepdf.open(pdf_path, password=password) as pdf:
        return len(pdf.pages)


# ──────────────────────────────────────────────────────────────
# Chain 1: Create blank PDF → Add page numbers → Extract text
# ──────────────────────────────────────────────────────────────

def test_chain_blank_add_numbers_extract_text(tmp_path):
    out = tmp_path / "out"
    out.mkdir()

    # Step 1: create blank PDF (3 pages)
    blank_path = create_blank_pdf(str(out), num_pages=3)
    assert Path(blank_path).exists()

    # Step 2: add page numbers
    numbered_path = add_page_numbers(blank_path, str(out), fmt="decimal", start_number=1)
    assert Path(numbered_path).exists()

    # Step 3: extract text (blank pages may have page numbers)
    result = extract_text_from_pdf(numbered_path, str(out))
    assert Path(result["output_path"]).exists()
    assert result["page_count"] == 3

    # The page numbers should appear as digits in the extracted text
    text_content = Path(result["output_path"]).read_text(encoding="utf-8")
    # Page numbers "1", "2", "3" should be present somewhere
    assert any(str(n) in text_content for n in [1, 2, 3])


# ──────────────────────────────────────────────────────────────
# Chain 2: Create PDF from text → Compress → Protect
# ──────────────────────────────────────────────────────────────

def test_chain_text_compress_protect(tmp_path):
    # Each step gets its own directory: a same-extension step's branded output
    # name is derived from the same original stem every time, so reusing one
    # directory across chained pdf->pdf steps would have it write over the
    # very file it just read as input.
    out1 = tmp_path / "out1"
    out1.mkdir()
    out2 = tmp_path / "out2"
    out2.mkdir()
    out3 = tmp_path / "out3"
    out3.mkdir()

    # Step 1: create PDF from text
    text_pdf = create_pdf_from_text(str(out1), content="Hello compress and protect chain test.")
    assert Path(text_pdf).exists()

    # Step 2: compress
    compress_result = compress_pdf(text_pdf, str(out2))
    compressed_path = compress_result["output_path"]
    assert Path(compressed_path).exists()

    # Step 3: protect
    protected_path = protect_pdf(compressed_path, str(out3), user_password=_TEST_PW)
    assert Path(protected_path).exists()

    # Verify it's password protected: opening without password should fail
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(protected_path)

    # Opening with password should succeed
    with pikepdf.open(protected_path, password=_TEST_PW) as pdf:
        assert len(pdf.pages) >= 1


# ──────────────────────────────────────────────────────────────
# Chain 3: Image → PDF → Extract text
# ──────────────────────────────────────────────────────────────

def test_chain_image_to_pdf_extract_text(tmp_path):
    out = tmp_path / "out"
    out.mkdir()

    # Step 1: create image
    img_path = _make_png_image(tmp_path)

    # Step 2: images to PDF
    pdf_path = images_to_pdf([str(img_path)], str(out))
    assert Path(pdf_path).exists()

    # Step 3: extract text (image-only PDF, text may be empty but should not crash)
    result = extract_text_from_pdf(pdf_path, str(out))
    assert Path(result["output_path"]).exists()
    assert result["page_count"] == 1


# ──────────────────────────────────────────────────────────────
# Chain 4: Multi-page PDF → Organize (reorder) → Add page numbers → verify page count
# ──────────────────────────────────────────────────────────────

def test_chain_multipage_organize_number(tmp_path):
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    out = tmp_path / "out"
    out.mkdir()

    # Create a 5-page PDF
    pdf_file = tmp_path / "multi.pdf"
    c = rl_canvas.Canvas(str(pdf_file), pagesize=A4)
    for i in range(1, 6):
        c.drawString(100, 750, f"Page {i}")
        c.showPage()
    c.save()

    # Step 1: organize - reorder to [5,4,3,2,1]
    reordered_path = organize_pdf(str(pdf_file), str(out), page_order=[5, 4, 3, 2, 1])
    assert _page_count(reordered_path) == 5

    # Step 2: add page numbers (separate dir — same original stem would
    # otherwise re-derive the same branded name organize_pdf just wrote to)
    out2 = tmp_path / "out2"
    out2.mkdir()
    numbered_path = add_page_numbers(reordered_path, str(out2))
    assert Path(numbered_path).exists()
    assert _page_count(numbered_path) == 5


# ──────────────────────────────────────────────────────────────
# Chain 5: Create PDF → Annotate → Metadata edit
# ──────────────────────────────────────────────────────────────

def test_chain_create_annotate_metadata(tmp_path):
    out1 = tmp_path / "out1"
    out1.mkdir()
    out2 = tmp_path / "out2"
    out2.mkdir()
    out3 = tmp_path / "out3"
    out3.mkdir()

    # Step 1: create PDF from text
    pdf_path = create_pdf_from_text(str(out1), content="Chain 5: annotation and metadata test.")
    assert Path(pdf_path).exists()

    # Step 2: annotate
    annotations = [{"type": "highlight", "page": 1, "rect": [50, 700, 300, 730]}]
    annotated_path = annotate_pdf(pdf_path, str(out2), annotations)
    assert Path(annotated_path).exists()

    # Step 3: edit metadata
    meta_path = edit_pdf_metadata(annotated_path, str(out3), title="Chain 5 PDF", author="Tester")
    assert Path(meta_path).exists()

    # Verify metadata was written
    with pikepdf.open(meta_path) as pdf:
        assert str(pdf.docinfo.get("/Title", "")) == "Chain 5 PDF"
        assert str(pdf.docinfo.get("/Author", "")) == "Tester"


# ──────────────────────────────────────────────────────────────
# Chain 6: Word to PDF → Rotate → Protect
# ──────────────────────────────────────────────────────────────

def test_chain_word_rotate_protect(tmp_path):
    out1 = tmp_path / "out1"
    out1.mkdir()
    out2 = tmp_path / "out2"
    out2.mkdir()
    out3 = tmp_path / "out3"
    out3.mkdir()

    # Step 1: create a DOCX and convert to PDF
    docx_path = _make_docx(tmp_path)
    pdf_path = word_to_pdf(str(docx_path), str(out1))
    assert Path(pdf_path).exists()
    assert _page_count(pdf_path) >= 1

    # Step 2: rotate 90 degrees
    rotated_path = rotate_pdf(pdf_path, str(out2), angle=90)
    assert Path(rotated_path).exists()

    # Step 3: protect
    protected_path = protect_pdf(rotated_path, str(out3), user_password=_TEST_PW)
    assert Path(protected_path).exists()

    # Verify password protection
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(protected_path)

    with pikepdf.open(protected_path, password=_TEST_PW) as pdf:
        assert len(pdf.pages) >= 1


# ──────────────────────────────────────────────────────────────
# No artificial per-step delay (issue #14)
#
# execute_workflow used to `await asyncio.sleep(1.0)` before every step so the
# UI animation was guaranteed visible, and started the timer *after* the sleep
# so /admin/stats couldn't see the cost. A minimum visible duration is now held
# client-side (MIN_STEP_VISIBLE_MS in static/script.js) instead.
# ──────────────────────────────────────────────────────────────

def test_workflow_does_not_sleep_between_steps(auth_client, tmp_path):
    """An N-step chain of trivial rotations must not cost ~N seconds of dead time."""
    import json
    import time

    src = create_blank_pdf(str(tmp_path), num_pages=1)

    steps = json.dumps([{"type": "rotate_pdf", "config": {"angle": 90}}] * 4)
    with open(src, "rb") as f:
        started = time.perf_counter()
        resp = auth_client.post(
            "/api/workflow/execute",
            files={"file": ("chain.pdf", f, "application/pdf")},
            data={"steps": steps},
        )
        body = resp.text
        elapsed = time.perf_counter() - started

    assert resp.status_code == 200
    assert '"event": "complete"' in body or "'event': 'complete'" in body, body
    # Four rotations of a blank page are milliseconds of real work. The old code
    # spent 4s sleeping; anything near that means the delay is back.
    assert elapsed < 2.0, f"4-step chain took {elapsed:.2f}s — artificial delay reintroduced?"


def test_workflow_source_has_no_sleep_call():
    """Belt to the timing test's braces: wall-clock bounds get flaky on loaded CI."""
    import inspect
    import main

    source = inspect.getsource(main.execute_workflow)
    assert "asyncio.sleep" not in source, (
        "execute_workflow must not sleep; hold the animation client-side instead"
    )
