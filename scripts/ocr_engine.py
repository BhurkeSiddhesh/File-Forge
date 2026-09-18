"""OCR backend abstraction for Forge Files.

Supports multiple OCR engines behind a common interface so the app can
run on ARM64 (via RapidOCR/ONNX Runtime) without requiring PaddlePaddle,
while preserving the Paddle backend as an optional high-quality engine on x86.

Configuration:
    OCR_BACKEND env var (default: "rapidocr")
        "rapidocr"  → RapidOCR (ARM64-compatible, ONNX Runtime)
        "paddle"    → PaddleOCR PPStructure (x86 only, best layout recovery)
        "none" / "" → No OCR engine (AI features disabled)

    DISABLE_AI env var (default: "0")
        "1" → forces OCR_BACKEND to "none" regardless of OCR_BACKEND value
"""

import os
import threading
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Abstract base
# ---------------------------------------------------------------------------

SUPPORTED_INDIC_LANGS = {
    "hi": "devanagari",
    "mr": "devanagari",
    "ta": "ta",
    "te": "te",
}

SUPPORTED_OCR_LANGUAGES = {"en", "hi", "mr", "ta", "te"}


class OCREngine(ABC):
    """Common interface for OCR backends used by pdf_utils."""

    @abstractmethod
    def recognize(self, image_path_or_array, lang: str = "en") -> List[Dict[str, Any]]:
        """Run OCR on an image with optional language specification.

        Returns list of dicts:
            [{"text": str, "bbox": list, "confidence": float}, ...]
        """
        ...

    @property
    @abstractmethod
    def name(self) -> str:
        ...

    @property
    def supports_layout(self) -> bool:
        """Whether this engine can do full layout recovery (tables, figures)."""
        return False


# ---------------------------------------------------------------------------
# RapidOCR backend (ARM64-compatible, lightweight)
# ---------------------------------------------------------------------------

def _to_plain_list(value):
    """Convert numpy arrays (or None) to plain Python lists."""
    if value is None:
        return []
    if hasattr(value, "tolist"):
        return value.tolist()
    return list(value)


class RapidOCREngine(OCREngine):
    """OCR via RapidOCR (ONNX Runtime).

    Uses PaddleOCR-trained model weights exported to ONNX, giving
    near-identical text accuracy with cross-platform portability.

    Handles both RapidOCR APIs:
      - rapidocr >= 2.0: engine(img) returns a RapidOCROutput object
        with .boxes / .txts / .scores attributes.
      - rapidocr_onnxruntime 1.x: engine(img) returns (result, elapse)
        where result is [[box, text, score], ...].

    Maintains a strict single-language memory model: only one recognition
    model is loaded at a time, evicting the previous model on language change.
    """

    def __init__(self, default_lang: str = "en"):
        self._current_spec: Optional[str] = None
        self._engine = None
        self._lock = threading.Lock()
        self._load_engine_for_spec(self._resolve_spec(default_lang))

    @property
    def name(self) -> str:
        return "rapidocr"

    @property
    def current_spec(self) -> Optional[str]:
        return self._current_spec

    def _resolve_spec(self, lang: str) -> str:
        clean = (lang or "en").strip().lower()
        if clean == "en":
            return "en"
        if clean in SUPPORTED_INDIC_LANGS:
            return SUPPORTED_INDIC_LANGS[clean]
        raise ValueError(
            f"Unsupported OCR language: {lang!r}. Supported languages are: "
            f"{', '.join(sorted(SUPPORTED_OCR_LANGUAGES))}."
        )

    def _load_engine_for_spec(self, spec: str):
        if self._current_spec == spec and self._engine is not None:
            return

        # Evict existing model to strictly bound memory
        if self._engine is not None:
            logger.info("Evicting RapidOCR model for '%s' to load '%s'", self._current_spec, spec)
            self._engine = None
            import gc
            gc.collect()

        try:
            from rapidocr import RapidOCR  # rapidocr >= 2.0
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR  # legacy 1.x package

        if spec == "en":
            self._engine = RapidOCR()
        else:
            params = {}
            try:
                from rapidocr.utils.typings import OCRVersion, ModelType, LangRec
                if spec == "devanagari":
                    params = {
                        "Global.use_cls": False,
                        "Rec.ocr_version": OCRVersion.PPOCRV4,
                        "Rec.model_type": ModelType.MOBILE,
                        "Rec.lang_type": LangRec.DEVANAGARI,
                    }
                elif spec == "ta":
                    params = {
                        "Global.use_cls": False,
                        "Rec.ocr_version": OCRVersion.PPOCRV4,
                        "Rec.model_type": ModelType.MOBILE,
                        "Rec.lang_type": LangRec.TA,
                    }
                elif spec == "te":
                    params = {
                        "Global.use_cls": False,
                        "Rec.ocr_version": OCRVersion.PPOCRV4,
                        "Rec.model_type": ModelType.MOBILE,
                        "Rec.lang_type": LangRec.TE,
                    }
            except (ImportError, AttributeError):
                logger.warning("RapidOCR typings not available; using default initialization for %s", spec)
                params = {}

            self._engine = RapidOCR(params=params) if params else RapidOCR()

        self._current_spec = spec
        logger.info("RapidOCR engine initialized for spec '%s'", spec)

    def recognize(self, image_path_or_array, lang: str = "en") -> List[Dict[str, Any]]:
        spec = self._resolve_spec(lang)
        lock = getattr(self, "_lock", None)
        if lock is not None:
            with lock:
                if getattr(self, "_current_spec", None) != spec or getattr(self, "_engine", None) is None:
                    self._load_engine_for_spec(spec)
                engine = self._engine
        else:
            engine = getattr(self, "_engine", None)

        raw = engine(image_path_or_array)

        # rapidocr_onnxruntime 1.x: (result, elapse) tuple
        if isinstance(raw, tuple):
            result = raw[0]
            return [
                {
                    "text": str(item[1]),
                    "confidence": float(item[2]),
                    "bbox": _to_plain_list(item[0]),
                }
                for item in (result or [])
            ]

        # rapidocr 2.x: RapidOCROutput object
        txts = getattr(raw, "txts", None) or ()
        scores = getattr(raw, "scores", None) or ()
        boxes = _to_plain_list(getattr(raw, "boxes", None))
        items: List[Dict[str, Any]] = []
        for i, text in enumerate(txts):
            if not text:
                continue
            items.append({
                "text": str(text),
                "confidence": float(scores[i]) if i < len(scores) else 0.0,
                "bbox": boxes[i] if i < len(boxes) else [],
            })
        return items


# ---------------------------------------------------------------------------
# PaddleOCR backend (x86 only, best quality)
# ---------------------------------------------------------------------------

class PaddleOCREngine(OCREngine):
    """OCR via PaddleOCR PPStructure (x86_64, ONNX mode).

    Delegates to pdf_utils.get_paddle_engine() so the PPStructure singleton
    (and its model-path resolution) has a single source of truth.
    """

    def __init__(self):
        # Deferred import avoids a circular import at module load time
        # (pdf_utils imports this module inside its functions).
        from scripts import pdf_utils
        self._engine = pdf_utils.get_paddle_engine()

    @property
    def name(self) -> str:
        return "paddle"

    @property
    def supports_layout(self) -> bool:
        return True

    def recognize(self, image_path_or_array, lang: str = "en") -> List[Dict[str, Any]]:
        result = self._engine(image_path_or_array)

        items: List[Dict[str, Any]] = []
        for block in (result or []):
            if not isinstance(block, dict):
                continue
            # PPStructure returns layout blocks whose text lines live in "res".
            res = block.get("res")
            if isinstance(res, list):
                for line in res:
                    if isinstance(line, dict) and line.get("text"):
                        items.append({
                            "text": str(line["text"]),
                            "confidence": float(line.get("confidence", 0.0)),
                            "bbox": _to_plain_list(line.get("text_region")),
                        })
            elif block.get("text"):
                items.append({
                    "text": str(block["text"]),
                    "confidence": float(block.get("score", 0.0)),
                    "bbox": _to_plain_list(block.get("bbox")),
                })
        return items


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------

# Module-level cache so get_ocr_engine() returns a singleton
_ocr_engine: Optional[OCREngine] = None
_ocr_engine_lock = threading.Lock()
_ocr_engine_loaded = False


def get_ocr_engine(backend: Optional[str] = None) -> Optional[OCREngine]:
    """Return the configured OCR engine (singleton), or None if AI is disabled.

    The backend is determined on first call and cached thereafter.
    Pass an explicit ``backend`` to bypass the cache (useful for tests).
    """
    global _ocr_engine, _ocr_engine_loaded

    if _ocr_engine_loaded and backend is None:
        return _ocr_engine

    with _ocr_engine_lock:
        if _ocr_engine_loaded and backend is None:
            return _ocr_engine

        if os.environ.get("DISABLE_AI", "0") == "1":
            chosen = "none"
        else:
            chosen = (backend or os.environ.get("OCR_BACKEND", "rapidocr")).strip().lower()

        if chosen == "paddle":
            engine: Optional[OCREngine] = PaddleOCREngine()
        elif chosen == "rapidocr":
            engine = RapidOCREngine()
        elif chosen in ("none", ""):
            engine = None
        else:
            raise ValueError(f"Unknown OCR_BACKEND: {chosen!r}")

        # Only cache env-driven selection; explicit overrides stay one-shot.
        if backend is None:
            _ocr_engine = engine
            _ocr_engine_loaded = True
        logger.info("OCR backend selected: %s", engine.name if engine else "none")
        return engine


def reset_engine():
    """Reset the engine cache — only for testing."""
    global _ocr_engine, _ocr_engine_loaded
    with _ocr_engine_lock:
        _ocr_engine = None
        _ocr_engine_loaded = False
