"""Build original, public teaching fixtures through the real processing utilities.

Run from public/: python -m scripts.build_content_examples
Synthetic documents only; never put a customer document in this directory.
The manifest records exact sizes, hashes, settings and library versions so the
published examples can be checked without treating them as a benchmark.
"""
from __future__ import annotations

import hashlib
import importlib.metadata
import json
import logging
import shutil
import tempfile
from pathlib import Path

import fitz
from PIL import Image, ImageDraw
from reportlab.lib import colors
from reportlab.pdfgen import canvas

from scripts import image_utils, pdf_utils

LOG = logging.getLogger(__name__)
DEST = Path(__file__).resolve().parents[1] / "static" / "examples"
REVIEW_DATE = "2026-09-26"


def report(path: Path, *, appendix: bool = False) -> None:
    """An original three-page workshop report, or a one-page appendix."""
    c = canvas.Canvas(str(path), pagesize=(595, 842), invariant=1)
    c.setTitle("Forge Files practice document - synthetic data")
    c.setAuthor("Forge Files")
    for page in range(1, 2 if appendix else 4):
        c.setFillColor(colors.HexColor("#17634b"))
        c.rect(0, 748, 595, 94, fill=1, stroke=0)
        c.setFillColor(colors.white)
        c.setFont("Helvetica-Bold", 23)
        c.drawString(44, 791, "Workshop notes" if not appendix else "Workshop appendix")
        c.setFont("Helvetica", 11)
        c.drawString(44, 768, "FORGE FILES / ORIGINAL PRACTICE DOCUMENT")
        c.setFillColor(colors.HexColor("#1f2937"))
        c.setFont("Helvetica-Bold", 17)
        c.drawString(44, 703, ["1. Materials and quantities", "2. Assembly checklist", "3. Handover notes"][page - 1])
        c.setFont("Helvetica", 11)
        lines = [
            "This document uses invented workshop data for testing file conversions.",
            "It contains selectable text, a simple table and deliberately small labels.",
            "Use it to check reading order, page boundaries and editable table cells.",
            "No customer information, signatures or personal records are included.",
        ]
        for i, line in enumerate(lines):
            c.drawString(44, 675 - i * 19, line)
        rows = [("Item", "Quantity", "Unit"), ("Wood panels", "12", "pieces"),
                ("Steel brackets", "24", "pieces"), ("Water-based finish", "3", "litres")]
        for row, values in enumerate(rows):
            y = 543 - row * 32
            c.setFillColor(colors.HexColor("#e5f2ec") if row == 0 else colors.white)
            c.rect(44, y, 507, 32, fill=1, stroke=0)
            c.setStrokeColor(colors.HexColor("#c4d3cc"))
            c.line(44, y, 551, y)
            c.setFillColor(colors.HexColor("#1f2937"))
            c.setFont("Helvetica-Bold" if row == 0 else "Helvetica", 11)
            for x, value in zip((54, 322, 434), values):
                c.drawString(x, y + 11, value)
        c.setFont("Helvetica-Bold", 13)
        c.drawString(44, 374, "Inspect after conversion")
        c.setFont("Helvetica", 11)
        for i, line in enumerate(("Check that quantities remain beside the correct items.",
                                  "Compare line breaks and spacing with this original PDF.",
                                  "A readable preview does not prove that every word is editable.")):
            c.drawString(44, 346 - i * 19, line)
        # Thin rules, small text and color ramps make scan compression visible.
        c.setFont("Helvetica", 7)
        c.drawString(44, 246, "Fine-print test: 0123456789 / Brackets 24 / Finish 3 litres")
        for i in range(100):
            c.setFillColor(colors.Color(i / 100, .45, 1 - i / 100))
            c.rect(44 + i * 5.07, 186, 5.2, 35, fill=1, stroke=0)
        c.setStrokeColor(colors.HexColor("#17634b"))
        c.setLineWidth(.35)
        for i in range(12):
            c.line(44, 159 - i * 2, 551, 159 - i * 2)
        c.setFillColor(colors.HexColor("#54655e"))
        c.setFont("Helvetica", 9)
        c.drawString(44, 65, "Synthetic fixture. Keep your own originals before processing.")
        c.drawRightString(551, 65, f"Page {page}" if not appendix else "Appendix")
        c.showPage()
    c.save()


def build() -> None:
    DEST.mkdir(parents=True, exist_ok=True)
    report(DEST / "report.pdf")
    report(DEST / "appendix.pdf", appendix=True)
    with fitz.open(DEST / "report.pdf") as doc:
        doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(DEST / "report-preview.png")
        scan = doc[0].get_pixmap(matrix=fitz.Matrix(4, 4))
        with fitz.open() as raster:
            page = raster.new_page(width=595, height=842)
            page.insert_image(page.rect, stream=scan.tobytes("png"))
            raster.save(DEST / "scan.pdf", deflate=True)
    measurements: dict = {}
    with tempfile.TemporaryDirectory(prefix="ff-examples-") as tmp:
        for level in ("low", "medium", "high"):
            result = pdf_utils.compress_pdf(str(DEST / "scan.pdf"), tmp, level=level)
            shutil.copyfile(result["output_path"], DEST / f"scan-{level}.pdf")
            measurements[level] = {key: result[key] for key in ("original_size", "compressed_size", "reduction_pct")}
        converted = pdf_utils.pdf_to_docx(str(DEST / "report.pdf"), tmp)
        shutil.copyfile(converted, DEST / "report.docx")
        merged = pdf_utils.merge_pdfs([str(DEST / "report.pdf"), str(DEST / "appendix.pdf")], tmp)
        shutil.copyfile(merged, DEST / "merged.pdf")
        extracted = pdf_utils.extract_pdf_pages(str(DEST / "report.pdf"), tmp, "1,3")
        shutil.copyfile(extracted, DEST / "extracted.pdf")
        # Generated diagnostic image, not an iPhone photo or camera benchmark.
        pattern = Image.new("RGB", (1200, 800), "white")
        draw = ImageDraw.Draw(pattern)
        for x in range(1200):
            draw.line((x, 0, x, 500), fill=(int(x * 255 / 1199), 115, 255 - int(x * 255 / 1199)))
        for i in range(12):
            draw.rectangle((40 + i * 95, 550, 100 + i * 95, 690), fill=(20 * i, 150, 40))
        draw.text((40, 735), "Forge Files / synthetic HEIC compatibility sample / 1200 x 800", fill="black")
        pattern.save(DEST / "pattern.heic", format="HEIF", quality=90)
        jpg = image_utils.heic_to_jpeg(str(DEST / "pattern.heic"), tmp, quality=95)
        shutil.copyfile(jpg, DEST / "pattern.jpg")
    for name, output in (("scan.pdf", "scan-before.png"), ("scan-high.pdf", "scan-after.png")):
        with fitz.open(DEST / name) as doc:
            doc[0].get_pixmap(matrix=fitz.Matrix(1.2, 1.2)).save(DEST / output)
    files = {}
    for path in sorted(DEST.iterdir()):
        if path.name == "manifest.json" or path.name.startswith(".") or not path.is_file():
            continue
        item = {"bytes": path.stat().st_size, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        if path.suffix == ".pdf":
            with fitz.open(path) as doc:
                item["pages"] = len(doc)
                item["selectable_words"] = sum(len(p.get_text().split()) for p in doc)
        files[path.name] = item
    manifest = {
        "reviewed": REVIEW_DATE,
        "provenance": "Original synthetic fixtures generated by Forge Files. No customer files or stock images.",
        "method": "Local Python utilities from this repository; standard PDF-to-Word mode, HEIC JPEG quality 95. Browser processing and production runtime may differ.",
        "reproduce": "From public/: python -m scripts.build_content_examples",
        "versions": {pkg: importlib.metadata.version(pkg) for pkg in ("PyMuPDF", "pdf2docx", "Pillow", "pillow-heif", "reportlab")},
        "compression": measurements,
        "files": files,
    }
    (DEST / "manifest.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    LOG.info("Built %d teaching files in %s", len(files), DEST)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build()
