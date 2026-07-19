"""Tests for the OCR backend abstraction (scripts/ocr_engine.py)."""
import sys
import types
from unittest.mock import MagicMock

import pytest

import scripts.ocr_engine as ocr_engine


class FakeRapidOCROutputV2:
    """Mimics rapidocr>=2.0 RapidOCROutput."""

    def __init__(self, txts=(), scores=(), boxes=()):
        self.txts = txts
        self.scores = scores
        self.boxes = boxes


@pytest.fixture(autouse=True)
def reset_engine_cache():
    ocr_engine.reset_engine()
    yield
    ocr_engine.reset_engine()


@pytest.fixture
def fake_rapidocr(monkeypatch):
    """Install a fake `rapidocr` module whose engine returns a v2 output object."""
    engine_instance = MagicMock()
    engine_instance.return_value = FakeRapidOCROutputV2(
        txts=("Hello", "World"),
        scores=(0.99, 0.87),
        boxes=([[0, 0], [10, 0], [10, 10], [0, 10]],
               [[0, 20], [10, 20], [10, 30], [0, 30]]),
    )
    module = types.ModuleType("rapidocr")
    module.RapidOCR = MagicMock(return_value=engine_instance)
    monkeypatch.setitem(sys.modules, "rapidocr", module)
    return engine_instance


class TestRapidOCREngine:
    def test_recognize_normalizes_v2_output(self, fake_rapidocr):
        engine = ocr_engine.RapidOCREngine()
        items = engine.recognize("fake_image.png")
        assert items == [
            {"text": "Hello", "confidence": 0.99,
             "bbox": [[0, 0], [10, 0], [10, 10], [0, 10]]},
            {"text": "World", "confidence": 0.87,
             "bbox": [[0, 20], [10, 20], [10, 30], [0, 30]]},
        ]

    def test_recognize_normalizes_v1_tuple_output(self, fake_rapidocr):
        # rapidocr_onnxruntime 1.x returned (result, elapse)
        fake_rapidocr.return_value = (
            [[[[0, 0], [5, 0], [5, 5], [0, 5]], "Legacy", 0.5]],
            0.1,
        )
        engine = ocr_engine.RapidOCREngine()
        items = engine.recognize("fake_image.png")
        assert items == [
            {"text": "Legacy", "confidence": 0.5,
             "bbox": [[0, 0], [5, 0], [5, 5], [0, 5]]},
        ]

    def test_recognize_handles_empty_result(self, fake_rapidocr):
        fake_rapidocr.return_value = FakeRapidOCROutputV2(txts=None, scores=None, boxes=None)
        engine = ocr_engine.RapidOCREngine()
        assert engine.recognize("fake_image.png") == []

    def test_name_and_layout_support(self, fake_rapidocr):
        engine = ocr_engine.RapidOCREngine()
        assert engine.name == "rapidocr"
        assert engine.supports_layout is False


class TestPaddleOCREngine:
    def test_delegates_to_pdf_utils_singleton(self, monkeypatch):
        import scripts.pdf_utils as pdf_utils
        fake_ppstructure = MagicMock()
        monkeypatch.setattr(pdf_utils, "get_paddle_engine", lambda: fake_ppstructure)

        engine = ocr_engine.PaddleOCREngine()
        assert engine.name == "paddle"
        assert engine.supports_layout is True
        assert engine._engine is fake_ppstructure

    def test_recognize_flattens_ppstructure_blocks(self, monkeypatch):
        import scripts.pdf_utils as pdf_utils
        fake_ppstructure = MagicMock(return_value=[
            {"type": "text", "res": [
                {"text": "line one", "confidence": 0.9, "text_region": [[0, 0], [1, 0], [1, 1], [0, 1]]},
                {"text": "line two", "confidence": 0.8},
            ]},
            {"type": "figure", "res": []},
        ])
        monkeypatch.setattr(pdf_utils, "get_paddle_engine", lambda: fake_ppstructure)

        engine = ocr_engine.PaddleOCREngine()
        items = engine.recognize("fake_image.png")
        assert [i["text"] for i in items] == ["line one", "line two"]


class TestGetOcrEngine:
    def test_rapidocr_backend(self, fake_rapidocr, monkeypatch):
        # DISABLE_AI overrides every backend, so clear it to test selection in
        # isolation (the CI matrix runs one job with DISABLE_AI=1 in the env).
        monkeypatch.delenv("DISABLE_AI", raising=False)
        engine = ocr_engine.get_ocr_engine("rapidocr")
        assert isinstance(engine, ocr_engine.RapidOCREngine)

    def test_paddle_backend(self, monkeypatch):
        monkeypatch.delenv("DISABLE_AI", raising=False)
        import scripts.pdf_utils as pdf_utils
        monkeypatch.setattr(pdf_utils, "get_paddle_engine", lambda: MagicMock())
        engine = ocr_engine.get_ocr_engine("paddle")
        assert isinstance(engine, ocr_engine.PaddleOCREngine)

    def test_none_backend_returns_none(self):
        assert ocr_engine.get_ocr_engine("none") is None

    def test_unknown_backend_raises(self, monkeypatch):
        monkeypatch.delenv("DISABLE_AI", raising=False)
        with pytest.raises(ValueError, match="Unknown OCR_BACKEND"):
            ocr_engine.get_ocr_engine("tesseract")

    def test_disable_ai_overrides_backend(self, monkeypatch):
        monkeypatch.setenv("DISABLE_AI", "1")
        monkeypatch.setenv("OCR_BACKEND", "rapidocr")
        assert ocr_engine.get_ocr_engine() is None

    def test_env_driven_selection_is_cached(self, monkeypatch, fake_rapidocr):
        monkeypatch.delenv("DISABLE_AI", raising=False)
        monkeypatch.setenv("OCR_BACKEND", "rapidocr")
        first = ocr_engine.get_ocr_engine()
        second = ocr_engine.get_ocr_engine()
        assert first is second
        assert isinstance(first, ocr_engine.RapidOCREngine)
