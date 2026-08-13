"""Tests for SSE progress streaming on PDF→Word conversion (Issue #46)."""
import json
import logging
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

import pytest

import scripts.pdf_utils as pdf_utils

try:
    import paddleocr  # noqa: F401
except ImportError:
    # paddleocr is a heavy optional dependency; stub it so PPStructure can be
    # patched in environments where it isn't installed (e.g. lightweight CI).
    sys.modules["paddleocr"] = MagicMock()


def _parse_sse(body: str):
    events = []
    for block in body.split("\n\n"):
        if block.startswith("data: "):
            events.append(json.loads(block[len("data: "):]))
    return events


class TestConvertToWordStream:
    def test_standard_conversion_streams_complete_event(self, auth_client, sample_pdf, tmp_path):
        with open(sample_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("text/event-stream")

        events = _parse_sse(resp.text)
        kinds = [e["event"] for e in events]
        assert kinds[0] == "start"
        assert "complete" in kinds, f"expected complete event, got: {kinds}"
        complete = next(e for e in events if e["event"] == "complete")
        assert complete["filename"].endswith(".docx")

    def test_error_is_streamed_not_raised(self, auth_client, tmp_path):
        bad = tmp_path / "broken.pdf"
        bad.write_bytes(b"this is not a pdf")
        with open(bad, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("broken.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        # SSE responses always return 200; errors arrive as events
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        assert any(e["event"] == "error" for e in events)

    def test_start_event_carries_a_job_id(self, auth_client, sample_pdf):
        """job_id lets a client that reconnects after a dropped SSE stream
        recover the result via GET /api/jobs/{job_id} (issue #95)."""
        with open(sample_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        events = _parse_sse(resp.text)
        start = events[0]
        assert start["event"] == "start"
        assert start["job_id"]

    def test_job_status_recoverable_after_stream_ends(self, auth_client, sample_pdf):
        """Even though the SSE connection is long closed by the time the test
        reads the response, the job's outcome must still be fetchable by id --
        this is what a client polls after a dropped connection instead of
        losing the result."""
        with open(sample_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        events = _parse_sse(resp.text)
        job_id = events[0]["job_id"]
        complete = next(e for e in events if e["event"] == "complete")

        job_resp = auth_client.get(f"/api/jobs/{job_id}")
        assert job_resp.status_code == 200
        job = job_resp.json()
        assert job["status"] == "done"
        assert job["event"] == complete

    def test_job_status_404_for_unknown_id(self, auth_client):
        assert auth_client.get("/api/jobs/does-not-exist-1234567890").status_code == 404

    def test_job_status_404_for_malformed_id(self, auth_client):
        assert auth_client.get("/api/jobs/../../etc/passwd").status_code in (404, 400)

    def test_no_auth_required(self, sample_pdf):
        from fastapi.testclient import TestClient
        from main import app
        client = TestClient(app)  # API is fully public — no credentials needed
        with open(sample_pdf, "rb") as f:
            resp = client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        assert resp.status_code != 403

    def test_ai_checkbox_on_text_pdf_stream_reports_accurate_message(self, auth_client, text_rich_pdf):
        """Checking "Use AI Layout Recovery" on a text-based PDF must not
        claim AI Layout Recovery happened when the server actually skipped
        OCR and used the PDF's own text layer."""
        with open(text_rich_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word-stream",
                files={"file": ("resume.pdf", f, "application/pdf")},
                data={"use_ai": "true"},
            )
        assert resp.status_code == 200
        events = _parse_sse(resp.text)
        complete = next(e for e in events if e["event"] == "complete")
        assert complete["method"] == "text_layer"
        assert "AI Layout Recovery" not in complete["message"]


class TestAiCapabilities:
    """/api/ai-capabilities lets the frontend describe what the deployed AI
    backend can actually do (e.g. RapidOCR on ARM has no layout recovery)
    instead of a single hard-coded "High Fidelity" claim."""

    def test_reports_disabled_when_ai_off(self, auth_client, monkeypatch):
        monkeypatch.setattr("main.DISABLE_AI", True)
        resp = auth_client.get("/api/ai-capabilities")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": False, "supports_layout": None}

    def test_reports_supports_layout_from_engine(self, auth_client, monkeypatch):
        import scripts.ocr_engine as ocr_engine

        monkeypatch.setattr("main.DISABLE_AI", False)
        fake_engine = MagicMock()
        fake_engine.supports_layout = True
        monkeypatch.setattr(ocr_engine, "get_ocr_engine", lambda *a, **k: fake_engine)

        resp = auth_client.get("/api/ai-capabilities")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "supports_layout": True}

    def test_reports_no_layout_support_for_rapidocr(self, auth_client, monkeypatch):
        import scripts.ocr_engine as ocr_engine

        monkeypatch.setattr("main.DISABLE_AI", False)
        fake_engine = MagicMock()
        fake_engine.supports_layout = False
        monkeypatch.setattr(ocr_engine, "get_ocr_engine", lambda *a, **k: fake_engine)

        resp = auth_client.get("/api/ai-capabilities")
        assert resp.status_code == 200
        assert resp.json() == {"enabled": True, "supports_layout": False}


class TestConvertToWord:
    def test_ai_checkbox_on_text_pdf_reports_accurate_message(self, auth_client, text_rich_pdf):
        with open(text_rich_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word",
                files={"file": ("resume.pdf", f, "application/pdf")},
                data={"use_ai": "true"},
            )
        assert resp.status_code == 200
        data = resp.json()
        assert "AI Layout Recovery" not in data["message"]
        assert "text layer" in data["message"].lower()


class TestProgressCallback:
    def test_pdf_to_word_ai_accepts_progress_callback(self):
        """The signature must accept progress_callback for SSE streaming."""
        import inspect
        sig = inspect.signature(pdf_utils.pdf_to_word_ai)
        assert "progress_callback" in sig.parameters

    def test_pdf_to_word_paddle_alias_preserved(self):
        """Pre-ARM-migration name must keep working for old callers."""
        assert pdf_utils.pdf_to_word_paddle is pdf_utils.pdf_to_word_ai

    @pytest.mark.parametrize("multiprocessing_on", ["1", "0"])
    def test_standard_conversion_reports_progress(self, multi_page_pdf, tmp_path,
                                                  monkeypatch, multiprocessing_on):
        """The standard converter is the slower of the two on long documents,
        and it used to stream nothing between "start" and a result minutes
        later — the SSE endpoint exists precisely to avoid that.

        Both modes are covered because they expose different amounts of
        pdf2docx's logging: serial reports its parsing and writing passes,
        multiprocessing parses in subprocesses so only writing is visible.
        """
        monkeypatch.setenv("PDF2DOCX_MULTIPROCESSING", multiprocessing_on)
        calls = []
        out = pdf_utils.pdf_to_docx(
            str(multi_page_pdf), str(tmp_path), None,
            progress_callback=lambda done, total: calls.append((done, total)),
        )

        assert Path(out).exists()
        assert calls, "no progress reported"
        # A bar that jumps backwards reads as a failure to anyone watching it.
        assert all(b[0] >= a[0] for a, b in zip(calls, calls[1:])), calls
        assert calls[-1][0] == calls[-1][1], f"did not finish at 100%: {calls[-1]}"
        assert calls[-1][1] == 4  # the fixture's page count

    def test_progress_handler_ignores_other_threads(self):
        """It attaches to the ROOT logger, so in a server running concurrent
        conversions it would otherwise report one request's pages into
        another's stream."""
        calls = []
        handler = pdf_utils._Pdf2docxProgress(lambda d, t: calls.append((d, t)),
                                              single_pass=True)
        mine = logging.LogRecord("root", logging.INFO, "", 0, "(2/7) Page 2", (), None)
        theirs = logging.LogRecord("root", logging.INFO, "", 0, "(5/7) Page 5", (), None)
        theirs.thread = handler._thread + 1

        handler.emit(mine)
        handler.emit(theirs)
        assert calls == [(2, 7)]

    def test_progress_handler_never_breaks_a_conversion(self):
        """Progress reporting must never be load-bearing: a callback that
        raises has to be swallowed, not take the conversion down with it."""
        def boom(done, total):
            raise RuntimeError("callback exploded")

        handler = pdf_utils._Pdf2docxProgress(boom, single_pass=True)
        record = logging.LogRecord("root", logging.INFO, "", 0, "(1/3) Page 1", (), None)
        record.thread = handler._thread
        handler.emit(record)  # must not raise

    def test_missing_system_library_becomes_an_actionable_error(self, tmp_path, monkeypatch):
        """A host missing OpenCV's runtime libraries failed every PDF→Word run
        with "libGL.so.1: cannot open shared object file" — a message that
        invites the user to go re-save their PDF, which cannot possibly help.
        """
        import pdf2docx

        def explode(*args, **kwargs):
            raise ImportError(
                "libGL.so.1: cannot open shared object file: No such file or directory"
            )

        monkeypatch.setattr(pdf2docx, "Converter", explode)

        with pytest.raises(pdf_utils.ServerDependencyError) as excinfo:
            pdf_utils._convert_pdf2docx("in.pdf", tmp_path / "out.docx")

        message = str(excinfo.value)
        assert "not a problem with your file" in message
        # The library is still named, so an operator reading the logs or the
        # error knows exactly which package is missing.
        assert "libGL.so.1" in message

    def test_missing_dependency_is_a_503_not_a_400(self, auth_client, sample_pdf, monkeypatch):
        """A missing server component is not a bad request. Reporting it as one
        blames the user's file and tells uptime monitoring nothing is wrong."""
        def explode(*args, **kwargs):
            raise pdf_utils.ServerDependencyError("PDF to Word is unavailable here.")

        monkeypatch.setattr("main.pdf_to_docx", explode)
        with open(sample_pdf, "rb") as f:
            resp = auth_client.post(
                "/api/pdf/convert-to-word",
                files={"file": ("sample.pdf", f, "application/pdf")},
                data={"use_ai": "false"},
            )
        assert resp.status_code == 503
        assert "unavailable" in resp.json()["detail"]

    def test_failed_multiprocessing_is_remembered(self, multi_page_pdf, tmp_path, monkeypatch):
        """The serial retry costs a second full conversion. The causes of a
        failed pass are environmental, not per-document, so paying that on
        every request means every conversion silently costs double."""
        monkeypatch.setenv("PDF2DOCX_MULTIPROCESSING", "1")
        monkeypatch.setattr(pdf_utils, "_multiprocessing_broken", False)
        attempts = []

        real_converter = pdf_utils.__dict__.get("_convert_pdf2docx")
        assert real_converter is not None

        class FakeConverter:
            def __init__(self, path):
                pass

            def convert(self, out, multi_processing=False):
                attempts.append(multi_processing)
                if multi_processing:
                    raise RuntimeError("cannot fork here")
                Path(out).write_text("docx")

            def close(self):
                pass

        import pdf2docx
        monkeypatch.setattr(pdf2docx, "Converter", FakeConverter)

        pdf_utils._convert_pdf2docx("in.pdf", tmp_path / "a.docx")
        assert attempts == [True, False], "first call should try multiprocessing then retry"

        pdf_utils._convert_pdf2docx("in.pdf", tmp_path / "b.docx")
        # Second conversion goes straight to serial instead of paying double again.
        assert attempts == [True, False, False]

    def test_progress_callback_invoked_per_page(self, multi_page_pdf, tmp_path, monkeypatch):
        """Drive pdf_to_word_ai (paddle backend) with mocked OCR and verify callbacks fire."""
        import scripts.ocr_engine as ocr_engine

        calls = []

        fake_engine = MagicMock(return_value=[])

        # Force the paddle backend; PaddleOCREngine delegates to the
        # (monkeypatched) pdf_utils.get_paddle_engine singleton.
        monkeypatch.delenv("DISABLE_AI", raising=False)
        monkeypatch.setenv("OCR_BACKEND", "paddle")
        ocr_engine.reset_engine()

        def fake_save_structure_res(*args, **kwargs):
            pass

        def fake_sorted_layout_boxes(result, w):
            return result

        def fake_convert_info_docx(img, res, temp_dir, page_name):
            # Simulate the recovery module writing the per-page docx
            from docx import Document
            doc = Document()
            doc.add_paragraph(f"content {page_name}")
            doc.save(f"{temp_dir}/{page_name}_ocr.docx")

        monkeypatch.setattr(pdf_utils, "get_paddle_engine", lambda: fake_engine)

        paddle_stub = MagicMock()
        paddle_stub.save_structure_res = fake_save_structure_res
        recovery_stub = MagicMock()
        recovery_stub.sorted_layout_boxes = fake_sorted_layout_boxes
        recovery_stub.convert_info_docx = fake_convert_info_docx

        try:
            with patch.dict(sys.modules, {
                "paddleocr": paddle_stub,
                "paddleocr.ppstructure": MagicMock(),
                "paddleocr.ppstructure.recovery": MagicMock(),
                "paddleocr.ppstructure.recovery.recovery_to_doc": recovery_stub,
            }):
                output = pdf_utils.pdf_to_word_ai(
                    str(multi_page_pdf),
                    str(tmp_path),
                    progress_callback=lambda done, total: calls.append((done, total)),
                )
        finally:
            # Drop the cached paddle-backed engine so other tests get a fresh pick
            ocr_engine.reset_engine()

        assert output.endswith(".docx")
        # 4-page fixture: initial (0, 4) plus one call per page
        assert calls[0] == (0, 4)
        assert calls[-1] == (4, 4)
        assert len(calls) == 5
