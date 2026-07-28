"""
Regression coverage for intermediate-file cleanup in /api/workflow/execute.

A chained workflow renames each non-final step's output to a throwaway uuid name
so the next step can consume it (see test_workflow_chain_naming.py for why the
rename exists). Those intermediates are NOT the deliverable and were previously
never deleted — they piled up on disk until the periodic stale-file sweep,
filling the disk on the resource-constrained VM, and every intermediate leaked
on a mid-workflow failure too. execute_workflow now deletes them in its `finally`
while preserving the final deliverable for the client's follow-up download.

Each run writes into its own result directory under OUTPUT_DIR, named by the
download token (see main.new_result_dir), so "what is left in OUTPUT_DIR" means
the run's own directory and "what is left of the run" means its contents.

These tests assert:
  1. a successful N-step chain leaves exactly the deliverable, no intermediates;
  2. a chain that fails after a successful step leaves NO orphaned intermediate,
     and no empty result directory either;
  3. a single-step workflow still preserves its deliverable (cleanup is not
     over-aggressive).
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
    doc.add_paragraph("Workflow cleanup regression test content.")
    p = tmp_path / name
    doc.save(str(p))
    return p


def _complete_event(sse_text):
    for line in sse_text.splitlines():
        if line.startswith("data: ") and '"event": "complete"' in line:
            return json.loads(line[len("data: "):])
    return None


def _has_error(sse_text):
    return any(
        line.startswith("data: ") and '"event": "error"' in line
        for line in sse_text.splitlines()
    )


def test_multistep_chain_leaves_only_deliverable(mock_dirs, auth_client, tmp_path):
    """A 3-step chain must leave exactly ONE file in OUTPUT_DIR — the deliverable
    — not the two throwaway intermediates it renamed along the way."""
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
    event = _complete_event(response.text)
    assert event is not None
    deliverable = event["filename"]

    # One result directory for the run, and exactly the deliverable inside it.
    # Before the fix this was 3 files (deliverable + 2 orphaned uuid-prefixed
    # intermediates).
    run_dirs = sorted(mock_dirs["output"].iterdir())
    assert [d.name for d in run_dirs] == [event["download_token"]], run_dirs
    assert sorted(p.name for p in run_dirs[0].iterdir()) == [deliverable]
    assert result_path(mock_dirs["output"], event).exists()
    # The upload temp is always cleaned already; confirm it still is.
    assert list(mock_dirs["upload"].iterdir()) == []


def test_failed_chain_cleans_intermediates(mock_dirs, auth_client, tmp_path):
    """When a chain fails after a successful step, the successful step's
    intermediate output must not be left orphaned in OUTPUT_DIR."""
    docx_path = _make_docx(tmp_path)
    # Step 1 (word_to_pdf) succeeds and its output is renamed to an intermediate;
    # step 2 (organize_pdf with empty page_order) hits the early error return.
    steps = json.dumps([
        {"type": "word_to_pdf", "config": {}, "label": "Word to PDF"},
        {"type": "organize_pdf", "config": {}, "label": "Organize PDF"},
    ])

    with open(docx_path, "rb") as f:
        files = {"file": (docx_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    assert _has_error(response.text)
    # No deliverable was produced, so nothing should remain — the step-1
    # intermediate (which leaked before the fix) must be gone, and the run's
    # now-empty result directory must not be left behind either.
    assert list(mock_dirs["output"].iterdir()) == []
    assert list(mock_dirs["upload"].iterdir()) == []


def test_single_step_workflow_preserves_deliverable(mock_dirs, auth_client, tmp_path):
    """Cleanup must never touch the deliverable: a one-step workflow (no
    intermediate rename at all) still leaves its output for download."""
    docx_path = _make_docx(tmp_path)
    steps = json.dumps([
        {"type": "word_to_pdf", "config": {}, "label": "Word to PDF"},
    ])

    with open(docx_path, "rb") as f:
        files = {"file": (docx_path.name, f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
        response = auth_client.post("/api/workflow/execute", files=files, data={"steps": steps})

    assert response.status_code == 200
    event = _complete_event(response.text)
    assert event is not None
    deliverable = event["filename"]

    run_dirs = sorted(mock_dirs["output"].iterdir())
    assert [d.name for d in run_dirs] == [event["download_token"]], run_dirs
    assert sorted(p.name for p in run_dirs[0].iterdir()) == [deliverable]
    assert result_path(mock_dirs["output"], event).exists()
