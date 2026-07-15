"""Behavioural tests for the compress_pdf rewrite.

The earlier bug: compress_pdf called doc.replace_image() (which doesn't exist on
Document in modern PyMuPDF — replace_image lives on Page), so image recompression
silently failed and every level produced identical, structural-only output. These
tests pin down the fixed behaviour:

  * every level (including 'low') actually shrinks an image-heavy PDF,
  * higher levels produce smaller files (low >= medium >= high),
  * the output is never larger than the input,
  * output is always a valid, openable PDF.
"""
import os

import pikepdf
import pytest

from scripts.pdf_utils import compress_pdf


@pytest.fixture(scope="module")
def image_pdf(tmp_path_factory):
    """A single-page PDF holding one large, high-entropy image.

    Random-noise pixels are effectively incompressible, so the only way to make
    the file smaller is the JPEG re-encode + downsample path — which is exactly
    the code that was broken. That makes this a faithful exercise of the fix.
    """
    import fitz  # PyMuPDF
    from PIL import Image

    d = tmp_path_factory.mktemp("image_pdf")
    w = h = 1600
    img = Image.frombytes("RGB", (w, h), os.urandom(w * h * 3))
    img_path = d / "noise.png"
    img.save(img_path)

    doc = fitz.open()
    page = doc.new_page(width=600, height=600)
    page.insert_image(page.rect, filename=str(img_path))
    pdf_path = d / "image.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def _sizes_by_level(image_pdf, tmp_path):
    results = {}
    for level in ("low", "medium", "high"):
        out = tmp_path / level
        out.mkdir()
        results[level] = compress_pdf(str(image_pdf), str(out), level=level)
    return results


def test_every_level_shrinks_image_pdf(image_pdf, tmp_path):
    """Including 'low' — which used to be a structural-only no-op."""
    results = _sizes_by_level(image_pdf, tmp_path)
    for level, r in results.items():
        assert r["compressed_size"] < r["original_size"], f"{level} did not shrink the file"
        assert r["reduction_pct"] > 0, f"{level} reported no reduction"


def test_higher_levels_produce_smaller_files(image_pdf, tmp_path):
    """low >= medium >= high, and high is strictly smaller than low."""
    r = _sizes_by_level(image_pdf, tmp_path)
    low, medium, high = (r["low"]["compressed_size"],
                         r["medium"]["compressed_size"],
                         r["high"]["compressed_size"])
    assert high <= medium <= low, f"levels not monotonic: low={low} medium={medium} high={high}"
    assert high < low, "high should be clearly smaller than low — levels are not differentiated"
    assert r["high"]["reduction_pct"] >= r["low"]["reduction_pct"]


def test_levels_produce_valid_pdfs(image_pdf, tmp_path):
    r = _sizes_by_level(image_pdf, tmp_path)
    for level, res in r.items():
        with pikepdf.open(res["output_path"]) as pdf:
            assert len(pdf.pages) == 1, f"{level} output is not a valid 1-page PDF"


def test_output_never_larger_than_input(sample_pdf, tmp_path):
    """Text-only PDFs barely compress; the guard must never hand back a bigger file."""
    for level in ("low", "medium", "high"):
        out = tmp_path / level
        out.mkdir()
        res = compress_pdf(str(sample_pdf), str(out), level=level)
        assert res["compressed_size"] <= res["original_size"], (
            f"{level} produced a file larger than the original"
        )


def test_unknown_level_falls_back_to_medium(image_pdf, tmp_path):
    """An unexpected level string must not crash — it defaults to medium."""
    res = compress_pdf(str(image_pdf), str(tmp_path), level="banana")
    assert res["compressed_size"] < res["original_size"]
