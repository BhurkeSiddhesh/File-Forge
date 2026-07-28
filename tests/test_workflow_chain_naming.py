"""
Regression coverage for multi-step /api/workflow/execute chains.

Two distinct bugs surfaced together once output filenames were branded as
"<original name>_forgefiles.org.<ext>" (see scripts/utils.py):

1. Idempotency: a chained step's input is the previous step's *already
   branded* output. original_stem() must strip a pre-existing brand suffix,
   not just the upload UUID prefix, or branding stacks every step
   ("name_forgefiles.org_forgefiles.org...").
2. Same-extension collision: once branding is idempotent, a same-extension
   step (e.g. rotate_pdf after word_to_pdf, or two chained pdf->pdf steps)
   computes the exact same output path as its input, and pikepdf refuses to
   overwrite a file it has open. execute_workflow renames each intermediate
   result off its branded name before the next step runs to avoid this.
"""
import json

import pytest
from unittest.mock import patch

from conftest import result_path


@pytest.fixture
def mock_dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield {"upload": upload_dir, "output": output_dir}


def _make_docx(tmp_path, name="report.docx"):
    from docx import Document
    doc = Document()
    doc.add_paragraph("Workflow chain naming regression test content.")
    p = tmp_path / name
    doc.save(str(p))
    return p


def _complete_event(sse_text):
    for line in sse_text.splitlines():
        if line.startswith("data: ") and '"event": "complete"' in line:
            return json.loads(line[len("data: "):])
    return None


def test_pdf_to_word_then_word_to_pptx_chain(sample_pdf, mock_dirs, auth_client):
    """The exact chain reported: PDF -> Word -> PowerPoint via the workflow builder."""
    steps = json.dumps([
        {"type": "pdf_to_word", "config": {}, "label": "PDF to Word"},
        {"type": "word_to_pptx", "config": {"dpi": 96}, "label": "Word to PowerPoint"},
    ])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "error" not in response.text
    event = _complete_event(response.text)
    assert event is not None

    filename = event["filename"]
    assert filename.endswith("_forgefiles.org.pptx")
    # The bug this guards against: branding stacking with every step.
    assert filename.count("forgefiles.org") == 1
    assert result_path(mock_dirs["output"], event).exists()


def test_same_extension_pdf_chain_does_not_collide(multi_page_pdf, mock_dirs, auth_client):
    """Two chained pdf->pdf steps must not have step 2 try to overwrite step 1's output."""
    steps = json.dumps([
        {"type": "rotate_pdf", "config": {"angle": 90}, "label": "Rotate PDF"},
        {"type": "compress_pdf", "config": {"level": "low"}, "label": "Compress PDF"},
    ])

    with open(multi_page_pdf, "rb") as f:
        files = {"file": (multi_page_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "error" not in response.text
    event = _complete_event(response.text)
    assert event is not None

    filename = event["filename"]
    assert filename.endswith("_forgefiles.org.pdf")
    assert filename.count("forgefiles.org") == 1
    assert result_path(mock_dirs["output"], event).exists()


def test_three_step_chain_stays_idempotent(mock_dirs, auth_client, tmp_path):
    """A longer chain still ends with exactly one brand suffix, not one per step."""
    docx_path = _make_docx(tmp_path)
    steps = json.dumps([
        {"type": "word_to_pdf", "config": {}, "label": "Word to PDF"},
        {"type": "rotate_pdf", "config": {"angle": 180}, "label": "Rotate PDF"},
        {"type": "compress_pdf", "config": {"level": "low"}, "label": "Compress PDF"},
    ])

    with open(docx_path, "rb") as f:
        files = {"file": (docx_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert "error" not in response.text
    event = _complete_event(response.text)
    assert event is not None

    filename = event["filename"]
    assert filename.endswith("_forgefiles.org.pdf")
    assert filename.count("forgefiles.org") == 1
    assert result_path(mock_dirs["output"], event).exists()
