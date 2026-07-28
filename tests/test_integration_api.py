import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import io
import json
import pytest
from fastapi.testclient import TestClient

# Suppress paddle/startup warnings before importing main
import os
os.environ.setdefault("FILE_FORGE_API_KEY", "")

from main import app

TEST_KEY = "test-secret-key"
AUTH_HEADERS = {"X-API-Key": TEST_KEY}


# ──────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────

def _make_client():
    app.state.api_key = TEST_KEY
    return TestClient(app, raise_server_exceptions=False)


def _make_simple_pdf() -> bytes:
    """Return a minimal 1-page PDF as bytes using reportlab."""
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    c.drawString(100, 750, "Hello, Integration Test!")
    c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _make_multi_page_pdf(pages: int = 3) -> bytes:
    from reportlab.pdfgen import canvas as rl_canvas
    from reportlab.lib.pagesizes import A4

    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=A4)
    for i in range(1, pages + 1):
        c.drawString(100, 750, f"Page {i} content")
        c.showPage()
    c.save()
    buf.seek(0)
    return buf.read()


def _make_docx() -> bytes:
    from docx import Document
    doc = Document()
    doc.add_paragraph("Hello from a DOCX file for testing.")
    buf = io.BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf.read()


def _make_png_image(w: int = 100, h: int = 100) -> bytes:
    from PIL import Image
    img = Image.new("RGB", (w, h), color=(255, 0, 0))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    buf.seek(0)
    return buf.read()


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/protect
# ──────────────────────────────────────────────────────────────

class TestProtectPDF:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/protect",
            headers=AUTH_HEADERS,
            data={"user_password": "mypassword"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "success"
        assert "filename" in data

    def test_returns_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/protect",
            headers=AUTH_HEADERS,
            data={"user_password": "pw"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_empty_password(self):
        # FastAPI may return 422 (Unprocessable Entity) or 400 (Bad Request)
        # for an empty required field — both indicate invalid input.
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/protect",
            headers=AUTH_HEADERS,
            data={"user_password": ""},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code in (400, 422)


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/rotate
# ──────────────────────────────────────────────────────────────

class TestRotatePDF:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/rotate",
            headers=AUTH_HEADERS,
            data={"angle": "90"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/rotate",
            headers=AUTH_HEADERS,
            data={"angle": "180"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_invalid_angle(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/rotate",
            headers=AUTH_HEADERS,
            data={"angle": "45"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/image/to-pdf
# ──────────────────────────────────────────────────────────────

class TestImageToPDF:
    def test_success(self):
        client = _make_client()
        img_bytes = _make_png_image()
        resp = client.post(
            "/api/image/to-pdf",
            headers=AUTH_HEADERS,
            files={"files": ("image.png", img_bytes, "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        img_bytes = _make_png_image()
        resp = client.post(
            "/api/image/to-pdf",
            headers=AUTH_HEADERS,
            files={"files": ("image.png", img_bytes, "image/png")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")



# ──────────────────────────────────────────────────────────────
# POST /api/word/to-pdf
# ──────────────────────────────────────────────────────────────

class TestWordToPDF:
    def test_success(self):
        client = _make_client()
        docx_bytes = _make_docx()
        resp = client.post(
            "/api/word/to-pdf",
            headers=AUTH_HEADERS,
            files={"file": ("test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        docx_bytes = _make_docx()
        resp = client.post(
            "/api/word/to-pdf",
            headers=AUTH_HEADERS,
            files={"file": ("test.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_415_invalid_file_type(self):
        client = _make_client()
        resp = client.post(
            "/api/word/to-pdf",
            headers=AUTH_HEADERS,
            files={"file": ("test.txt", b"plain text", "text/plain")},
        )
        # Rejected by the extension allowlist at intake, before the bytes ever
        # reach LibreOffice — 415, not the converter's own 400.
        assert resp.status_code == 415


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/to-excel
# ──────────────────────────────────────────────────────────────

class TestPDFToExcel:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/to-excel",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_xlsx_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/to-excel",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".xlsx")



# ──────────────────────────────────────────────────────────────
# POST /api/pdf/to-pptx
# ──────────────────────────────────────────────────────────────

class TestPDFToPPTX:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/to-pptx",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pptx_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/to-pptx",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pptx")



# ──────────────────────────────────────────────────────────────
# POST /api/pdf/extract-text
# ──────────────────────────────────────────────────────────────

class TestExtractText:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/extract-text",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_txt_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/extract-text",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".txt")



# ──────────────────────────────────────────────────────────────
# POST /api/pdf/organize
# ──────────────────────────────────────────────────────────────

class TestOrganizePDF:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_multi_page_pdf(3)
        resp = client.post(
            "/api/pdf/organize",
            headers=AUTH_HEADERS,
            data={"page_order": "2,1"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        pdf_bytes = _make_multi_page_pdf(2)
        resp = client.post(
            "/api/pdf/organize",
            headers=AUTH_HEADERS,
            data={"page_order": "1,2"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_out_of_range_page(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()  # 1 page
        resp = client.post(
            "/api/pdf/organize",
            headers=AUTH_HEADERS,
            data={"page_order": "1,5"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/add-page-numbers
# ──────────────────────────────────────────────────────────────

class TestAddPageNumbers:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/add-page-numbers",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/add-page-numbers",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_invalid_font_size(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/add-page-numbers",
            headers=AUTH_HEADERS,
            data={"font_size": "200"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/repair
# ──────────────────────────────────────────────────────────────

class TestRepairPDF:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/repair",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/repair",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")



# ──────────────────────────────────────────────────────────────
# POST /api/pdf/create-from-text
# ──────────────────────────────────────────────────────────────

class TestCreateFromText:
    def test_success(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-from-text",
            headers=AUTH_HEADERS,
            data={"content": "Hello World"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-from-text",
            headers=AUTH_HEADERS,
            data={"content": "Test content"},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_empty_content(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-from-text",
            headers=AUTH_HEADERS,
            data={"content": "   "},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/create-blank
# ──────────────────────────────────────────────────────────────

class TestCreateBlank:
    def test_success(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-blank",
            headers=AUTH_HEADERS,
            data={"num_pages": "2"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-blank",
            headers=AUTH_HEADERS,
            data={"num_pages": "1"},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_zero_pages(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-blank",
            headers=AUTH_HEADERS,
            data={"num_pages": "0"},
        )
        assert resp.status_code == 400

    def test_400_too_many_pages(self):
        client = _make_client()
        resp = client.post(
            "/api/pdf/create-blank",
            headers=AUTH_HEADERS,
            data={"num_pages": "200"},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/annotate
# ──────────────────────────────────────────────────────────────

class TestAnnotatePDF:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        annotations = json.dumps([
            {"type": "highlight", "page": 1, "rect": [50, 700, 300, 730]}
        ])
        resp = client.post(
            "/api/pdf/annotate",
            headers=AUTH_HEADERS,
            data={"annotations": annotations},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        annotations = json.dumps([
            {"type": "underline", "page": 1, "rect": [50, 700, 300, 730]}
        ])
        resp = client.post(
            "/api/pdf/annotate",
            headers=AUTH_HEADERS,
            data={"annotations": annotations},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")


    def test_400_invalid_json(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/annotate",
            headers=AUTH_HEADERS,
            data={"annotations": "not-valid-json"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 400


# ──────────────────────────────────────────────────────────────
# POST /api/pdf/metadata
# ──────────────────────────────────────────────────────────────

class TestMetadata:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/metadata",
            headers=AUTH_HEADERS,
            data={"title": "Test Title"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "filename" in resp.json()

    def test_returns_pdf_filename(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/metadata",
            headers=AUTH_HEADERS,
            data={"author": "Test Author"},
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["filename"].endswith(".pdf")



# ──────────────────────────────────────────────────────────────
# POST /api/pdf/metadata/read
# ──────────────────────────────────────────────────────────────

class TestMetadataRead:
    def test_success(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/metadata/read",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"
        assert "metadata" in resp.json()

    def test_metadata_has_page_count(self):
        client = _make_client()
        pdf_bytes = _make_simple_pdf()
        resp = client.post(
            "/api/pdf/metadata/read",
            headers=AUTH_HEADERS,
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert resp.status_code == 200
        metadata = resp.json()["metadata"]
        assert "page_count" in metadata

