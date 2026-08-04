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


@pytest.fixture(scope="module")
def transparent_image_pdf(tmp_path_factory):
    """A single-page PDF with one oversized image whose left half is fully
    transparent (alpha=0) over a blue page background, right half opaque red.

    Reproduces the compress_pdf transparency bug: PyMuPDF stores black under
    fully-transparent PNG pixels in the base image object (only the /SMask
    hides it), so re-encoding the base colour data as an opaque JPEG and
    dropping the mask painted solid black where the blue background used to
    show through.
    """
    import fitz
    from PIL import Image

    d = tmp_path_factory.mktemp("transparent_pdf")
    w = h = 1600  # above every level's max_dim so the alpha path actually re-encodes
    img = Image.new("RGBA", (w, h), (255, 0, 0, 255))
    for x in range(w // 2):
        for y in range(h):
            img.putpixel((x, y), (255, 0, 0, 0))
    img_path = d / "half_transparent.png"
    img.save(img_path)

    doc = fitz.open()
    page = doc.new_page(width=400, height=400)
    page.draw_rect(page.rect, color=(0, 0, 1), fill=(0, 0, 1))
    page.insert_image(page.rect, filename=str(img_path))
    pdf_path = d / "transparent.pdf"
    doc.save(str(pdf_path))
    doc.close()
    return pdf_path


def test_compress_preserves_transparency(transparent_image_pdf, tmp_path):
    """Compressing must not turn a transparent region opaque/black."""
    import fitz

    res = compress_pdf(str(transparent_image_pdf), str(tmp_path), level="high")
    assert res["compressed_size"] < res["original_size"]

    doc = fitz.open(res["output_path"])
    pix = doc[0].get_pixmap()
    # Transparent left half must still show the blue page background through it.
    assert pix.pixel(50, 200) == (0, 0, 255)
    # Opaque right half must remain the original red.
    assert pix.pixel(350, 200) == (255, 0, 0)
    doc.close()
