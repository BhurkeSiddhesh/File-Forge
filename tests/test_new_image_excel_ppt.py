import csv
import zipfile
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook
from PIL import Image
from pptx import Presentation
from pptx.util import Inches, Pt

from scripts.excel_utils import (
    csv_to_xlsx,
    excel_to_pdf,
    merge_excel_files,
    xlsx_to_csv,
)
from scripts.image_utils import (
    compress_image,
    convert_image_format,
    rotate_image,
    watermark_image,
)
from scripts.ppt_utils import merge_pptx, ppt_to_images_zip, ppt_to_pdf


# --- Fixtures ---

@pytest.fixture
def jpeg_image(tmp_path):
    p = tmp_path / "in.jpg"
    Image.new("RGB", (200, 100), color=(120, 80, 200)).save(p, "JPEG", quality=95)
    return p


@pytest.fixture
def png_image(tmp_path):
    p = tmp_path / "in.png"
    Image.new("RGBA", (160, 120), color=(255, 0, 0, 200)).save(p, "PNG")
    return p


@pytest.fixture
def csv_file(tmp_path):
    p = tmp_path / "data.csv"
    with p.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["name", "age", "city"])
        w.writerow(["alice", 30, "NYC"])
        w.writerow(["bob", 28, "SF"])
    return p


@pytest.fixture
def xlsx_file(tmp_path):
    p = tmp_path / "data.xlsx"
    wb = Workbook()
    ws = wb.active
    ws.title = "People"
    ws.append(["name", "age"])
    ws.append(["alice", 30])
    ws.append(["bob", 28])
    wb.save(p)
    return p


@pytest.fixture
def two_xlsx_files(tmp_path):
    paths = []
    for i in range(2):
        p = tmp_path / f"book_{i}.xlsx"
        wb = Workbook()
        ws = wb.active
        ws.title = f"Sheet_{i}"
        ws.append([f"file{i}_a", f"file{i}_b"])
        ws.append([1, 2])
        wb.save(p)
        paths.append(p)
    return paths


@pytest.fixture
def pptx_file(tmp_path):
    p = tmp_path / "deck.pptx"
    prs = Presentation()
    for i in range(2):
        slide = prs.slides.add_slide(prs.slide_layouts[5])  # title only
        title = slide.shapes.title
        title.text = f"Slide {i + 1}"
        # Add a freeform text box.
        tx = slide.shapes.add_textbox(Inches(1), Inches(2), Inches(4), Inches(1))
        tf = tx.text_frame
        tf.text = f"Body text {i + 1}"
        for run in tf.paragraphs[0].runs:
            run.font.size = Pt(20)
    prs.save(p)
    return p


@pytest.fixture
def two_pptx_files(tmp_path):
    paths = []
    for i in range(2):
        p = tmp_path / f"deck_{i}.pptx"
        prs = Presentation()
        slide = prs.slides.add_slide(prs.slide_layouts[5])
        slide.shapes.title.text = f"Deck {i} slide"
        prs.save(p)
        paths.append(p)
    return paths


# --- Image tests ---

def test_rotate_image_90_swaps_dimensions(jpeg_image, tmp_path):
    out = Path(rotate_image(str(jpeg_image), str(tmp_path), 90))
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (100, 200)


def test_rotate_image_rejects_bad_angle(jpeg_image, tmp_path):
    with pytest.raises(ValueError):
        rotate_image(str(jpeg_image), str(tmp_path), "abc")


def test_compress_image_reduces_size(jpeg_image, tmp_path):
    # Make the image a real photo-like one so JPEG q=10 actually compresses.
    big = tmp_path / "big.jpg"
    Image.new("RGB", (800, 800), (200, 100, 50)).save(big, "JPEG", quality=95)
    result = compress_image(str(big), str(tmp_path), quality=10)
    assert Path(result["output_path"]).exists()
    assert result["compressed_size"] <= result["original_size"]


def test_compress_image_rejects_bad_quality(jpeg_image, tmp_path):
    with pytest.raises(ValueError):
        compress_image(str(jpeg_image), str(tmp_path), quality=200)


def test_convert_image_to_png(jpeg_image, tmp_path):
    out = Path(convert_image_format(str(jpeg_image), str(tmp_path), "png"))
    assert out.exists()
    assert out.suffix == ".png"
    with Image.open(out) as img:
        assert img.format == "PNG"


def test_convert_image_to_webp(png_image, tmp_path):
    out = Path(convert_image_format(str(png_image), str(tmp_path), "webp"))
    assert out.exists()
    assert out.suffix == ".webp"


def test_convert_image_rejects_bad_format(jpeg_image, tmp_path):
    with pytest.raises(ValueError):
        convert_image_format(str(jpeg_image), str(tmp_path), "tiff")


def test_watermark_image_creates_output(jpeg_image, tmp_path):
    out = Path(watermark_image(str(jpeg_image), str(tmp_path), "DRAFT", position="diagonal"))
    assert out.exists()
    with Image.open(out) as img:
        assert img.size == (200, 100)


def test_watermark_image_rejects_empty_text(jpeg_image, tmp_path):
    with pytest.raises(ValueError):
        watermark_image(str(jpeg_image), str(tmp_path), "  ")


# --- Excel tests ---

def test_csv_to_xlsx_roundtrip(csv_file, tmp_path):
    out = Path(csv_to_xlsx(str(csv_file), str(tmp_path)))
    assert out.exists()
    wb = load_workbook(out)
    ws = wb.active
    rows = list(ws.iter_rows(values_only=True))
    assert rows[0] == ("name", "age", "city")
    assert rows[1][0] == "alice"


def test_xlsx_to_csv_first_sheet(xlsx_file, tmp_path):
    out = Path(xlsx_to_csv(str(xlsx_file), str(tmp_path)))
    assert out.exists()
    text = out.read_text(encoding="utf-8")
    assert "name,age" in text
    assert "alice,30" in text


def test_xlsx_to_csv_named_sheet(xlsx_file, tmp_path):
    out = Path(xlsx_to_csv(str(xlsx_file), str(tmp_path), sheet="People"))
    assert out.exists()


def test_xlsx_to_csv_unknown_sheet(xlsx_file, tmp_path):
    with pytest.raises(ValueError):
        xlsx_to_csv(str(xlsx_file), str(tmp_path), sheet="Nope")


def test_excel_to_pdf_creates_pdf(xlsx_file, tmp_path):
    out = Path(excel_to_pdf(str(xlsx_file), str(tmp_path)))
    assert out.exists()
    assert out.suffix == ".pdf"
    assert out.stat().st_size > 0


def test_merge_excel_combines_sheets(two_xlsx_files, tmp_path):
    out = Path(merge_excel_files([str(p) for p in two_xlsx_files], str(tmp_path)))
    assert out.exists()
    wb = load_workbook(out)
    # Each input had one sheet -> output has 2.
    assert len(wb.sheetnames) == 2


def test_merge_excel_requires_two(xlsx_file, tmp_path):
    with pytest.raises(ValueError):
        merge_excel_files([str(xlsx_file)], str(tmp_path))


# --- PPT tests ---

def test_ppt_to_images_zip_one_per_slide(pptx_file, tmp_path):
    result = ppt_to_images_zip(str(pptx_file), str(tmp_path), fmt="png")
    out = Path(result["output_path"])
    assert out.exists()
    assert result["slide_count"] == 2
    with zipfile.ZipFile(out) as zf:
        assert len(zf.namelist()) == 2


def test_ppt_to_pdf_creates_pdf(pptx_file, tmp_path):
    out = Path(ppt_to_pdf(str(pptx_file), str(tmp_path)))
    assert out.exists()
    assert out.suffix == ".pdf"
    assert out.stat().st_size > 0


def test_merge_pptx_combines_decks(two_pptx_files, tmp_path):
    out = Path(merge_pptx([str(p) for p in two_pptx_files], str(tmp_path)))
    assert out.exists()
    prs = Presentation(str(out))
    # Original first deck has 1 slide; appending the second deck's 1 slide -> 2 total.
    assert len(prs.slides) == 2


def test_merge_pptx_requires_two(pptx_file, tmp_path):
    with pytest.raises(ValueError):
        merge_pptx([str(pptx_file)], str(tmp_path))
