"""Tests for SSE progress streaming on PDF→Word conversion (Issue #46)."""
import json
import sys
from unittest.mock import patch, MagicMock

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


class TestProgressCallback:
    def test_pdf_to_word_ai_accepts_progress_callback(self):
        """The signature must accept progress_callback for SSE streaming."""
        import inspect
        sig = inspect.signature(pdf_utils.pdf_to_word_ai)
        assert "progress_callback" in sig.parameters

    def test_pdf_to_word_paddle_alias_preserved(self):
        """Pre-ARM-migration name must keep working for old callers."""
        assert pdf_utils.pdf_to_word_paddle is pdf_utils.pdf_to_word_ai

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
