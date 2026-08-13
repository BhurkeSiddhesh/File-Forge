"""
Coverage for workflow-builder step types that existed in the /api/workflow/execute
dispatcher but had no corresponding "add step" option in the frontend palette
(see static/index.html step-palette / static/script.js needsConfig()).

Each of these is exercised here through the actual endpoint to confirm the
backend step is reachable and functioning, matching what the palette now exposes.
"""
import json
from unittest.mock import patch

from conftest import result_path

import pytest
import pikepdf


@pytest.fixture
def mock_dirs(tmp_path):
    """Patches UPLOAD_DIR and OUTPUT_DIR to use temporary directories."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()

    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield {"upload": upload_dir, "output": output_dir}


def _make_docx(tmp_path):
    from docx import Document
    doc = Document()
    doc.add_paragraph("Workflow step coverage test DOCX content.")
    p = tmp_path / "coverage.docx"
    doc.save(str(p))
    return p


def test_api_workflow_pdf_to_pptx_step(sample_pdf, mock_dirs, auth_client):
    """A single-step workflow can convert PDF -> PowerPoint directly (the reported gap)."""
    steps = json.dumps([{"type": "pdf_to_pptx", "config": {"dpi": 96}, "label": "PDF to PowerPoint"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pptx" in response.text


def test_api_workflow_pdf_to_epub_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{"type": "pdf_to_epub", "config": {}, "label": "PDF to EPUB"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.epub" in response.text


def test_api_workflow_rotate_pdf_step(multi_page_pdf, mock_dirs, auth_client):
    steps = json.dumps([{"type": "rotate_pdf", "config": {"angle": 90}, "label": "Rotate PDF"}])

    with open(multi_page_pdf, "rb") as f:
        files = {"file": (multi_page_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_protect_pdf_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{
        "type": "protect_pdf",
        "config": {"user_password": "wf-test-pw"},
        "label": "Protect PDF",
    }])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text

    payload = [
        json.loads(line[len("data: "):])
        for line in response.text.splitlines()
        if line.startswith("data: ") and '"event": "complete"' in line
    ][0]
    output_path = result_path(mock_dirs["output"], payload)
    assert output_path.exists()
    with pytest.raises(pikepdf.PasswordError):
        pikepdf.open(output_path)
    with pikepdf.open(output_path, password="wf-test-pw") as pdf:
        assert len(pdf.pages) >= 1


def test_api_workflow_word_to_pdf_step(mock_dirs, auth_client, tmp_path):
    docx_path = _make_docx(tmp_path)
    steps = json.dumps([{"type": "word_to_pdf", "config": {}, "label": "Word to PDF"}])

    with open(docx_path, "rb") as f:
        files = {"file": (docx_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_pdf_to_excel_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{"type": "pdf_to_excel", "config": {}, "label": "PDF to Excel"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.xlsx" in response.text


def test_api_workflow_organize_pdf_step(multi_page_pdf, mock_dirs, auth_client):
    steps = json.dumps([{
        "type": "organize_pdf",
        "config": {"page_order": [2, 1]},
        "label": "Organize PDF",
    }])

    with open(multi_page_pdf, "rb") as f:
        files = {"file": (multi_page_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_organize_pdf_step_requires_page_order(sample_pdf, mock_dirs, auth_client):
    """Backend still rejects an empty page_order even though the UI now validates it too."""
    steps = json.dumps([{"type": "organize_pdf", "config": {}, "label": "Organize PDF"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "error" in response.text


def test_api_workflow_add_page_numbers_step(multi_page_pdf, mock_dirs, auth_client):
    steps = json.dumps([{
        "type": "add_page_numbers",
        "config": {"position": "bottom-center", "start_number": 1},
        "label": "Add Page Numbers",
    }])

    with open(multi_page_pdf, "rb") as f:
        files = {"file": (multi_page_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_repair_pdf_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{"type": "repair_pdf", "config": {}, "label": "Repair PDF"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_annotate_pdf_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{
        "type": "annotate_pdf",
        "config": {"annotations": [{"type": "highlight", "page": 1, "rect": [50, 700, 300, 730]}]},
        "label": "Annotate PDF",
    }])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text


def test_api_workflow_edit_metadata_step(sample_pdf, mock_dirs, auth_client):
    steps = json.dumps([{
        "type": "edit_metadata",
        "config": {"title": "Workflow Step Coverage Title"},
        "label": "Edit Metadata",
    }])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "complete" in response.text
    assert "_forgefiles.org.pdf" in response.text
