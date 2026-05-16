import importlib
import sys
from pathlib import Path

import pytest


def test_pdf_utils_import_without_optional_dependencies(monkeypatch):
    """Module import should succeed even if heavy optional deps are unavailable."""
    real_import = __import__

    def guarded_import(name, *args, **kwargs):
        if name in {"cv2", "pdf2docx", "fitz", "docxcompose", "docx"}:
            raise ImportError(f"simulated missing optional dependency: {name}")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", guarded_import)
    sys.modules.pop("scripts.pdf_utils", None)

    module = importlib.import_module("scripts.pdf_utils")

    assert hasattr(module, "remove_pdf_password")
    assert hasattr(module, "pdf_to_docx")


def test_resolve_models_dir_prefers_repo_models(monkeypatch):
    module = importlib.import_module("scripts.pdf_utils")
    fake_script = Path("/tmp/project/scripts/pdf_utils.py")
    monkeypatch.setattr(module, "__file__", str(fake_script))

    resolved = module._resolve_models_dir()
    assert str(resolved).endswith("/tmp/project/models")
