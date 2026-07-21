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

class OCREngine(ABC):
    """Common interface for OCR backends used by pdf_utils."""

    @abstractmethod
    def recognize(self, image_path_or_array) -> List[Dict[str, Any]]:
        """Run OCR on an image.

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
    """

    def __init__(self):
        try:
            from rapidocr import RapidOCR  # rapidocr >= 2.0
        except ImportError:
            from rapidocr_onnxruntime import RapidOCR  # legacy 1.x package
        self._engine = RapidOCR()
        logger.info("RapidOCR engine initialized")

    @property
    def name(self) -> str:
        return "rapidocr"

    def recognize(self, image_path_or_array) -> List[Dict[str, Any]]:
        raw = self._engine(image_path_or_array)

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

    def recognize(self, image_path_or_array) -> List[Dict[str, Any]]:
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
