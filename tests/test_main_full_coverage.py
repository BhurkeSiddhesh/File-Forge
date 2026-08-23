"""Full-branch coverage tests for public/main.py.

These tests target the per-endpoint error handlers (``except ValueError`` /
``except Exception`` -> HTTP 400), the ``finally`` cleanup paths where a
Windows-locked temp file raises ``PermissionError``, the workflow runner's
step dispatch table and error streams, and assorted module-level helpers
(rate limiters, stale-file sweeper, upload guards, SEO/ads builders).

Core processing functions are monkeypatched with fakes: error tests raise
out of the core, happy-path tests return a path (or result dict) without
touching heavy backends. ``download_fields`` only reads the path's *name*,
so fake outputs never need to exist on disk for the JSON endpoints. The
workflow runner is different: non-final step outputs are renamed on disk,
so workflow fakes create real files inside the result directory.
"""

import asyncio
import json as jsonlib
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient
from starlette.requests import Request

import main as m
from main import app


PDF_BYTES = b"%PDF-1.1\n1 0 obj\n<<>>\nendobj\n"
IMG_BYTES = b"\x89PNG\r\n\x1a\n" + b"\x00" * 64
EXE_BYTES = b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00" + b"\x00" * 128

PDF_FILE = ("file", ("doc.pdf", PDF_BYTES, "application/pdf"))
PNG_FILE = ("file", ("img.png", IMG_BYTES, "image/png"))
HEIC_FILE = ("file", ("img.heic", IMG_BYTES, "image/heic"))
XLSX_FILE = ("file", ("book.xlsx", b"PK\x03\x04 fake", "application/vnd.ms-excel"))
CSV_FILE = ("file", ("data.csv", b"a,b\n1,2\n", "text/csv"))
PPTX_FILE = ("file", ("deck.pptx", b"PK\x03\x04 fake", "application/vnd.ms-powerpoint"))
DOCX_FILE = ("file", ("doc.docx", b"PK\x03\x04 fake", "application/msword"))


def _post(client, case, files=None, data=None):
    return client.post(
        case["url"],
        files=files if files is not None else case.get("files"),
        data=data if data is not None else case.get("data"),
    )


def _mkfiles(field, filename, content, ctype, count):
    return [(field, (filename, content, ctype)) for _ in range(count)]


# --- fake core results -----------------------------------------------------

def _fake_path(*a, **k):
    return str(Path(a[1]) / "out.bin")


def _fake_path_dirfirst(*a, **k):
    return str(Path(a[0]) / "out.bin")


def _fake_compress(*a, **k):
    return {
        "output_path": str(Path(a[1]) / "out.bin"),
        "original_size": 2,
        "compressed_size": 1,
        "reduction_pct": 50,
    }


def _fake_pages(*a, **k):
    return {"output_path": str(Path(a[1]) / "out.zip"), "page_count": 1}


def _fake_slides(*a, **k):
    return {"output_path": str(Path(a[1]) / "out.zip"), "slide_count": 1}


def _fake_tables(*a, **k):
    return {"output_path": str(Path(a[1]) / "out.xlsx"), "tables_found": 1}


def _fake_repair(*a, **k):
    return {"output_path": str(Path(a[1]) / "out.pdf"), "repair_status": "repaired"}


def _fake_meta(*a, **k):
    return {"title": "t"}


OK_FAKES = {
    "path": _fake_path,
    "dirfirst": _fake_path_dirfirst,
    "compress": _fake_compress,
    "pages": _fake_pages,
    "slides": _fake_slides,
    "tables": _fake_tables,
    "repair": _fake_repair,
    "meta": _fake_meta,
}


def _raiser(exc):
    def f(*a, **k):
        raise exc
    return f


# (url, patch target, files, data, ok-kind, error kinds)
# error kinds: "ve" -> ValueError handler, "re" -> generic Exception handler
# (RuntimeError), "te" -> generic handler that follows an explicit
# RuntimeError handler (repair). "any" -> endpoint has a single generic
# handler, one raised exception covers it.
CASES = [
    pytest.param(dict(
        id="remove-password", url="/api/pdf/remove-password",
        target="main.remove_pdf_password", files=[PDF_FILE],
        data={"password": "x"}, ok="path", errs=("any",),
    ), id="remove-password"),
    pytest.param(dict(
        id="extract-pages", url="/api/pdf/extract-pages",
        target="main.extract_pdf_pages", files=[PDF_FILE],
        data={"pages": "1"}, ok="path", errs=("ve", "re"),
    ), id="extract-pages"),
    pytest.param(dict(
        id="compress", url="/api/pdf/compress",
        target="main.compress_pdf", files=[PDF_FILE],
        data={}, ok="compress", errs=("ve", "re"),
    ), id="compress"),
    pytest.param(dict(
        id="merge", url="/api/pdf/merge",
        target="main.merge_pdfs",
        files=_mkfiles("files", "a.pdf", PDF_BYTES, "application/pdf", 2),
        data={"passwords": "a,,b"}, ok="path", errs=("ve", "re"),
    ), id="merge"),
    pytest.param(dict(
        id="watermark", url="/api/pdf/watermark",
        target="main.add_watermark", files=[PDF_FILE],
        data={"text": "W"}, ok="path", errs=("ve", "re"),
    ), id="watermark"),
    pytest.param(dict(
        id="rotate", url="/api/pdf/rotate",
        target="main.rotate_pdf", files=[PDF_FILE],
        data={"angle": "90"}, ok="path", errs=("ve", "re"),
    ), id="rotate"),
    pytest.param(dict(
        id="to-images", url="/api/pdf/to-images",
        target="main.pdf_to_images_zip", files=[PDF_FILE],
        data={}, ok="pages", errs=("ve", "re"),
    ), id="to-images"),
    pytest.param(dict(
        id="sign", url="/api/pdf/sign",
        target="main.sign_pdf",
        files=[PDF_FILE, ("signature", ("sig.png", IMG_BYTES, "image/png"))],
        data={}, ok="path", errs=("ve", "re"),
    ), id="sign"),
    pytest.param(dict(
        id="heic-to-jpeg", url="/api/image/heic-to-jpeg",
        target="main.heic_to_jpeg", files=[HEIC_FILE],
        data={}, ok="path", errs=("any",),
    ), id="heic-to-jpeg"),
    pytest.param(dict(
        id="resize", url="/api/image/resize",
        target="scripts.image_utils.resize_image", files=[PNG_FILE],
        data={"mode": "percentage", "percentage": "50"}, ok="path", errs=("any",),
    ), id="resize"),
    pytest.param(dict(
        id="crop", url="/api/image/crop",
        target="scripts.image_utils.crop_image", files=[PNG_FILE],
        data={"x": "0", "y": "0", "width": "10", "height": "10"},
        ok="path", errs=("any",),
    ), id="crop"),
    pytest.param(dict(
        id="image-rotate", url="/api/image/rotate",
        target="main.rotate_image", files=[PNG_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="image-rotate"),
    pytest.param(dict(
        id="image-compress", url="/api/image/compress",
        target="main.compress_image", files=[PNG_FILE],
        data={}, ok="compress", errs=("ve", "re"),
    ), id="image-compress"),
    pytest.param(dict(
        id="image-convert", url="/api/image/convert",
        target="main.convert_image_format", files=[PNG_FILE],
        data={"target_format": "jpg"}, ok="path", errs=("ve", "re"),
    ), id="image-convert"),
    pytest.param(dict(
        id="image-watermark", url="/api/image/watermark",
        target="main.watermark_image", files=[PNG_FILE],
        data={"text": "W"}, ok="path", errs=("ve", "re"),
    ), id="image-watermark"),
    pytest.param(dict(
        id="excel-to-pdf", url="/api/excel/to-pdf",
        target="main.excel_to_pdf", files=[XLSX_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="excel-to-pdf"),
    pytest.param(dict(
        id="csv-to-xlsx", url="/api/excel/csv-to-xlsx",
        target="main.csv_to_xlsx", files=[CSV_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="csv-to-xlsx"),
    pytest.param(dict(
        id="xlsx-to-csv", url="/api/excel/xlsx-to-csv",
        target="main.xlsx_to_csv", files=[XLSX_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="xlsx-to-csv"),
    pytest.param(dict(
        id="excel-merge", url="/api/excel/merge",
        target="main.merge_excel_files",
        files=_mkfiles("files", "a.xlsx", b"PK\x03\x04 f", "application/vnd.ms-excel", 2),
        data={}, ok="path", errs=("ve", "re"),
    ), id="excel-merge"),
    pytest.param(dict(
        id="ppt-to-pdf", url="/api/ppt/to-pdf",
        target="main.ppt_to_pdf", files=[PPTX_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="ppt-to-pdf"),
    pytest.param(dict(
        id="ppt-to-images", url="/api/ppt/to-images",
        target="main.ppt_to_images_zip", files=[PPTX_FILE],
        data={}, ok="slides", errs=("ve", "re"),
    ), id="ppt-to-images"),
    pytest.param(dict(
        id="ppt-merge", url="/api/ppt/merge",
        target="main.merge_pptx",
        files=_mkfiles("files", "a.pptx", b"PK\x03\x04 f", "application/vnd.ms-powerpoint", 2),
        data={}, ok="path", errs=("ve", "re"),
    ), id="ppt-merge"),
    pytest.param(dict(
        id="protect", url="/api/pdf/protect",
        target="main.protect_pdf", files=[PDF_FILE],
        data={"user_password": "pw"}, ok="path", errs=("ve", "re"),
    ), id="protect"),
    pytest.param(dict(
        id="image-to-pdf", url="/api/image/to-pdf",
        target="main.images_to_pdf",
        files=_mkfiles("files", "a.png", IMG_BYTES, "image/png", 2),
        data={}, ok="path", errs=("ve", "re"),
    ), id="image-to-pdf"),
    pytest.param(dict(
        id="word-to-pdf", url="/api/word/to-pdf",
        target="main.word_to_pdf", files=[DOCX_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="word-to-pdf"),
    pytest.param(dict(
        id="word-to-pptx", url="/api/word/to-pptx",
        target="main.word_to_pptx", files=[DOCX_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="word-to-pptx"),
    pytest.param(dict(
        id="pdf-to-excel", url="/api/pdf/to-excel",
        target="main.pdf_to_excel", files=[PDF_FILE],
        data={}, ok="tables", errs=("ve", "re"),
    ), id="pdf-to-excel"),
    pytest.param(dict(
        id="pdf-to-pptx", url="/api/pdf/to-pptx",
        target="main.pdf_to_pptx", files=[PDF_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="pdf-to-pptx"),
    pytest.param(dict(
        id="pdf-to-epub", url="/api/pdf/to-epub",
        target="main.pdf_to_epub", files=[PDF_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="pdf-to-epub"),
    pytest.param(dict(
        id="extract-text", url="/api/pdf/extract-text",
        target="main.extract_text_from_pdf", files=[PDF_FILE],
        data={}, ok="pages", errs=("ve", "re"),
    ), id="extract-text"),
    pytest.param(dict(
        id="add-page-numbers", url="/api/pdf/add-page-numbers",
        target="main.add_page_numbers", files=[PDF_FILE],
        data={}, ok="path", errs=("ve", "re"),
    ), id="add-page-numbers"),
    pytest.param(dict(
        id="repair", url="/api/pdf/repair",
        target="main.repair_pdf", files=[PDF_FILE],
        data={}, ok="repair", errs=("re", "te"),
    ), id="repair"),
    pytest.param(dict(
        id="create-from-text", url="/api/pdf/create-from-text",
        target="main.create_pdf_from_text", files=None,
        data={"content": "hello"}, ok="dirfirst", errs=("ve", "re"),
    ), id="create-from-text"),
    pytest.param(dict(
        id="create-blank", url="/api/pdf/create-blank",
        target="main.create_blank_pdf", files=None,
        data={"num_pages": "1"}, ok="dirfirst", errs=("ve", "re"),
    ), id="create-blank"),
    pytest.param(dict(
        id="metadata", url="/api/pdf/metadata",
        target="main.edit_pdf_metadata", files=[PDF_FILE],
        data={"title": "T"}, ok="path", errs=("ve", "re"),
    ), id="metadata"),
    pytest.param(dict(
        id="metadata-read", url="/api/pdf/metadata/read",
        target="main.get_pdf_metadata", files=[PDF_FILE],
        data={}, ok="meta", errs=("any",),
    ), id="metadata-read"),
]


def _patch_target(monkeypatch, dotted, value):
    monkeypatch.setattr(dotted, value)


@pytest.mark.parametrize("case", [c.values[0] for c in CASES],
                         ids=[c.id for c in CASES])
def test_endpoint_value_error_returns_400(auth_client, monkeypatch, case):
    if "ve" not in case["errs"]:
        pytest.skip("endpoint has no dedicated ValueError handler")
    _patch_target(monkeypatch, case["target"], _raiser(ValueError("bad input")))
    r = _post(auth_client, case)
    assert r.status_code == 400


@pytest.mark.parametrize("case", [c.values[0] for c in CASES],
                         ids=[c.id for c in CASES])
def test_endpoint_unexpected_error_returns_400(auth_client, monkeypatch, case):
    if not any(k in case["errs"] for k in ("re", "any")):
        pytest.skip("covered by the RuntimeError-handler test")
    _patch_target(monkeypatch, case["target"], _raiser(RuntimeError("boom")))
    r = _post(auth_client, case)
    assert r.status_code == 400


def test_repair_generic_error_returns_400(auth_client, monkeypatch):
    """repair has except RuntimeError THEN except Exception; a TypeError must
    fall through the first into the second."""
    monkeypatch.setattr("main.repair_pdf", _raiser(TypeError("not runtime")))
    r = auth_client.post("/api/pdf/repair",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 400


@pytest.mark.parametrize("case", [c.values[0] for c in CASES],
                         ids=[c.id for c in CASES])
def test_endpoint_happy_path_with_locked_tempfile(auth_client, monkeypatch, case):
    """Core succeeds while os.remove raises PermissionError (Windows lock):
    the finally block must swallow it and the response stays a success."""
    monkeypatch.setattr(case["target"], OK_FAKES[case["ok"]])
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = _post(auth_client, case)
    assert r.status_code == 200
    assert r.json()["status"] == "success"


# --- endpoints with bespoke validation branches -----------------------------

def test_organize_json_bracket_form(auth_client, monkeypatch):
    """page_order='[2,1]' exercises the JSON-parse branch."""
    monkeypatch.setattr("main.organize_pdf", _fake_path)
    r = auth_client.post("/api/pdf/organize",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"page_order": "[2,1]"})
    assert r.status_code == 200


def test_organize_bad_page_order_400(auth_client):
    """Unparsable page_order raises ValueError before the core ever runs."""
    r = auth_client.post("/api/pdf/organize",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"page_order": "abc"})
    assert r.status_code == 400


def test_organize_core_error_400(auth_client, monkeypatch):
    monkeypatch.setattr("main.organize_pdf", _raiser(RuntimeError("x")))
    r = auth_client.post("/api/pdf/organize",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"page_order": "1"})
    assert r.status_code == 400


def test_annotate_non_list_400(auth_client):
    """annotations='{}' parses as JSON but is not a list."""
    r = auth_client.post("/api/pdf/annotate",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"annotations": "{}"})
    assert r.status_code == 400


def test_annotate_bad_json_400(auth_client):
    r = auth_client.post("/api/pdf/annotate",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"annotations": "not json"})
    assert r.status_code == 400


def test_annotate_core_error_400(auth_client, monkeypatch):
    monkeypatch.setattr("main.annotate_pdf", _raiser(RuntimeError("x")))
    r = auth_client.post("/api/pdf/annotate",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"annotations": "[]"})
    assert r.status_code == 400


def test_annotate_happy_locked_tempfile(auth_client, monkeypatch):
    monkeypatch.setattr("main.annotate_pdf", _fake_path)
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = auth_client.post("/api/pdf/annotate",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"annotations": "[]"})
    assert r.status_code == 200


def test_organize_happy_locked_tempfile(auth_client, monkeypatch):
    monkeypatch.setattr("main.organize_pdf", _fake_path)
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = auth_client.post("/api/pdf/organize",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"page_order": "1"})
    assert r.status_code == 200


# --- convert-to-word: dedicated ServerDependencyError handler ---------------

def test_convert_to_word_dependency_error_503(auth_client, monkeypatch):
    monkeypatch.setattr("main.pdf_to_docx", _raiser(m.ServerDependencyError("no libreoffice")))
    r = auth_client.post("/api/pdf/convert-to-word",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 503


def test_convert_to_word_generic_error_400(auth_client, monkeypatch):
    monkeypatch.setattr("main.pdf_to_docx", _raiser(RuntimeError("x")))
    r = auth_client.post("/api/pdf/convert-to-word",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 400


def test_convert_to_word_happy_locked_tempfile(auth_client, monkeypatch):
    monkeypatch.setattr("main.pdf_to_docx", _fake_path)
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = auth_client.post("/api/pdf/convert-to-word",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 200


def test_convert_to_word_ai_happy(auth_client, monkeypatch):
    def fake_ai(path, out_dir, password, method_callback=None):
        if method_callback:
            method_callback("paddle_layout")
        return str(Path(out_dir) / "out.docx")

    monkeypatch.setattr("main.pdf_to_word_ai", fake_ai)
    r = auth_client.post("/api/pdf/convert-to-word",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"use_ai": "true"})
    assert r.status_code == 200
    assert "AI Layout Recovery" in r.json()["message"]


def test_convert_to_word_stream_locked_tempfile(auth_client, monkeypatch):
    """The SSE endpoint's finally must swallow a PermissionError from
    os.remove (Windows lock) after the worker finishes."""
    def fake_docx(path, out_dir, password, progress_callback=None):
        if progress_callback:
            progress_callback(1, 1)
        return str(Path(out_dir) / "out.docx")

    monkeypatch.setattr("main.pdf_to_docx", fake_docx)
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = auth_client.post("/api/pdf/convert-to-word-stream",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 200
    assert '"event": "complete"' in r.text


# --- workflow runner ---------------------------------------------------------

def _wf_outdir(args):
    """The result dir is the only argument that is an existing directory
    (inputs are files, passwords/levels are plain strings)."""
    return next(Path(x) for x in args if isinstance(x, str) and Path(x).is_dir())


def _wf_path_fake(name):
    """Workflow fakes must create a real file: non-final step outputs are
    renamed on disk (Path.replace) before the next step consumes them."""
    def f(*a, **k):
        p = _wf_outdir(a) / f"wf_{name}.out"
        p.write_bytes(b"x")
        return str(p)
    return f


def _wf_dict_fake(name, extra):
    def f(*a, **k):
        p = _wf_outdir(a) / f"wf_{name}.out"
        p.write_bytes(b"x")
        return {"output_path": str(p), **extra}
    return f


WF_PATH_CORES = [
    "remove_pdf_password", "pdf_to_word_ai", "pdf_to_docx", "heic_to_jpeg",
    "rotate_image", "convert_image_format", "watermark_image", "excel_to_pdf",
    "csv_to_xlsx", "xlsx_to_csv", "ppt_to_pdf", "rotate_pdf", "protect_pdf",
    "word_to_pdf", "word_to_pptx", "pdf_to_pptx", "pdf_to_epub",
    "organize_pdf", "add_page_numbers", "annotate_pdf", "edit_pdf_metadata",
]
WF_DICT_CORES = {
    "compress_pdf": {"original_size": 2, "compressed_size": 1, "reduction_pct": 50},
    "compress_image": {"original_size": 2, "compressed_size": 1, "reduction_pct": 50},
    "ppt_to_images_zip": {"slide_count": 1},
    "pdf_to_excel": {"tables_found": 1},
    "extract_text_from_pdf": {"page_count": 1},
    "repair_pdf": {"repair_status": "ok"},
}


def _patch_workflow_cores(monkeypatch):
    for name in WF_PATH_CORES:
        monkeypatch.setattr(m, name, _wf_path_fake(name))
    for name, extra in WF_DICT_CORES.items():
        monkeypatch.setattr(m, name, _wf_dict_fake(name, extra))
    import scripts.image_utils as iu
    monkeypatch.setattr(iu, "resize_image", _wf_path_fake("resize"))
    monkeypatch.setattr(iu, "crop_image", _wf_path_fake("crop"))


def _post_workflow(client, steps):
    return client.post(
        "/api/workflow/execute",
        files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
        data={"steps": jsonlib.dumps(steps)},
    )


CHAIN_A = [  # exactly MAX_WORKFLOW_STEPS (20) steps
    {"type": "remove_password", "config": {"password": "x"}},
    {"type": "pdf_to_word", "config": {"use_ai": True}},
    {"type": "pdf_to_word", "config": {"use_ai": False}},
    {"type": "heic_to_jpeg", "config": {}},
    {"type": "resize_image", "config": {}},
    {"type": "crop_image", "config": {}},
    {"type": "compress_pdf", "config": {}},
    {"type": "rotate_image", "config": {}},
    {"type": "compress_image", "config": {}},
    {"type": "convert_image", "config": {}},
    {"type": "watermark_image", "config": {}},
    {"type": "excel_to_pdf", "config": {}},
    {"type": "csv_to_xlsx", "config": {}},
    {"type": "xlsx_to_csv", "config": {}},
    {"type": "ppt_to_pdf", "config": {}},
    {"type": "ppt_to_images", "config": {}},
    {"type": "rotate_pdf", "config": {}},
    {"type": "protect_pdf", "config": {"user_password": "u"}},
    {"type": "word_to_pdf", "config": {}},
    {"type": "word_to_pptx", "config": {}},
]

CHAIN_B = [
    {"type": "pdf_to_excel", "config": {}},
    {"type": "pdf_to_pptx", "config": {}},
    {"type": "pdf_to_epub", "config": {}},
    {"type": "extract_text", "config": {}},
    {"type": "organize_pdf", "config": {"page_order": [1]}},
    {"type": "add_page_numbers", "config": {}},
    {"type": "repair_pdf", "config": {}},
    {"type": "annotate_pdf", "config": {}},
    {"type": "edit_metadata", "config": {}},
]


def test_workflow_chain_a_all_step_types(auth_client, monkeypatch):
    _patch_workflow_cores(monkeypatch)
    r = _post_workflow(auth_client, CHAIN_A)
    assert r.status_code == 200
    assert '"event": "complete"' in r.text


def test_workflow_chain_b_all_step_types(auth_client, monkeypatch):
    _patch_workflow_cores(monkeypatch)
    r = _post_workflow(auth_client, CHAIN_B)
    assert r.status_code == 200
    assert '"event": "complete"' in r.text


def test_workflow_invalid_steps_json_400(auth_client):
    r = auth_client.post("/api/workflow/execute",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"steps": "not json"})
    assert r.status_code == 400


def test_workflow_steps_not_a_list_400(auth_client):
    r = auth_client.post("/api/workflow/execute",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"steps": "{}"})
    assert r.status_code == 400


def test_workflow_too_many_steps_400(auth_client):
    steps = [{"type": "rotate_pdf"}] * (m.MAX_WORKFLOW_STEPS + 1)
    r = _post_workflow(auth_client, steps)
    assert r.status_code == 400


def test_workflow_non_dict_step_400(auth_client):
    r = auth_client.post("/api/workflow/execute",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")},
                         data={"steps": jsonlib.dumps(["rotate_pdf"])})
    assert r.status_code == 400


def test_workflow_remove_password_missing(auth_client):
    r = _post_workflow(auth_client, [{"type": "remove_password", "config": {}}])
    assert "Password required" in r.text


def test_workflow_protect_missing_user_password(auth_client):
    r = _post_workflow(auth_client, [{"type": "protect_pdf", "config": {}}])
    assert "user_password required" in r.text


def test_workflow_organize_missing_page_order(auth_client):
    r = _post_workflow(auth_client, [{"type": "organize_pdf", "config": {}}])
    assert "page_order required" in r.text


def test_workflow_unknown_step(auth_client):
    r = _post_workflow(auth_client, [{"type": "no_such_step", "config": {}}])
    assert "Unknown step type" in r.text


def test_workflow_step_failure_streams_error(auth_client, monkeypatch):
    monkeypatch.setattr(m, "compress_pdf", _raiser(RuntimeError("core blew up")))
    r = _post_workflow(auth_client, [{"type": "compress_pdf", "config": {}}])
    assert '"event": "error"' in r.text
    assert "core blew up" in r.text


def test_workflow_cleanup_swallows_permission_error(auth_client, monkeypatch):
    _patch_workflow_cores(monkeypatch)
    monkeypatch.setattr(os, "remove", _raiser(PermissionError("locked")))
    r = _post_workflow(auth_client, [{"type": "rotate_pdf", "config": {}}])
    assert '"event": "complete"' in r.text


# --- upload guards ------------------------------------------------------------

def test_upload_dest_path_escape_400(monkeypatch):
    """A rigged uuid makes the resolved destination leave UPLOAD_DIR."""
    monkeypatch.setattr(m.uuid, "uuid4", lambda: "../evil")
    with pytest.raises(HTTPException) as exc_info:
        m._upload_dest(SimpleNamespace(filename="doc.pdf"), {".pdf"})
    assert exc_info.value.status_code == 400


def test_executable_upload_rejected_415(auth_client):
    r = auth_client.post(
        "/api/image/rotate",
        files={"file": ("evil.png", EXE_BYTES, "image/png")},
    )
    assert r.status_code == 415


def test_save_uploads_cleans_partial_batch(auth_client, monkeypatch, tmp_path):
    """A rejected later file must unlink the ones already written."""
    monkeypatch.setattr(m, "UPLOAD_DIR", tmp_path)
    r = auth_client.post(
        "/api/pdf/merge",
        files=[
            ("files", ("a.pdf", PDF_BYTES, "application/pdf")),
            ("files", ("b.txt", b"hello", "text/plain")),
        ],
    )
    assert r.status_code == 415
    assert list(tmp_path.iterdir()) == []


# --- rate limiters -------------------------------------------------------------

class _FakePipe:
    def __init__(self, client):
        self.client = client

    def zremrangebyscore(self, *a):
        return self

    def zcard(self, *a):
        return self

    def execute(self):
        return [None, self.client.count]


class _FakeRedis:
    def __init__(self, count=0, oldest=None):
        self.count = count
        self._oldest = oldest or []
        self.deleted = []

    def pipeline(self):
        return _FakePipe(self)

    def zrange(self, key, a, b, withscores=False):
        return self._oldest

    def zadd(self, *a, **k):
        pass

    def expire(self, *a):
        pass

    def scan_iter(self, match=""):
        return ["ff:rl:k1", "ff:rl:k2"]

    def delete(self, key):
        self.deleted.append(key)


def test_redis_limiter_check_allowed():
    client = _FakeRedis(count=0)
    limiter = m.RedisSlidingWindowRateLimiter(client)
    allowed, retry = limiter.check("ip:light", 5)
    assert allowed and retry == 0


def test_redis_limiter_check_blocked_with_oldest():
    client = _FakeRedis(count=5, oldest=[("member", time.time() - 1.0)])
    limiter = m.RedisSlidingWindowRateLimiter(client)
    allowed, retry = limiter.check("ip:light", 1)
    assert not allowed
    assert retry >= 1


def test_redis_limiter_check_blocked_without_oldest():
    client = _FakeRedis(count=5, oldest=[])
    limiter = m.RedisSlidingWindowRateLimiter(client)
    allowed, retry = limiter.check("ip:light", 1)
    assert not allowed
    assert retry >= 1


def test_redis_limiter_prune_and_reset():
    client = _FakeRedis()
    limiter = m.RedisSlidingWindowRateLimiter(client)
    assert limiter.prune() == 0
    limiter.reset()
    assert client.deleted == ["ff:rl:k1", "ff:rl:k2"]


def test_build_rate_limiter_redis_success(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    fake_client = SimpleNamespace(ping=lambda: True)
    fake_redis = SimpleNamespace(
        Redis=SimpleNamespace(from_url=lambda url, decode_responses=True: fake_client)
    )
    monkeypatch.setitem(sys.modules, "redis", fake_redis)
    limiter = m.build_rate_limiter()
    assert isinstance(limiter, m.RedisSlidingWindowRateLimiter)


def test_build_rate_limiter_redis_package_missing(monkeypatch):
    monkeypatch.setenv("REDIS_URL", "redis://example:6379/0")
    monkeypatch.setitem(sys.modules, "redis", None)
    with pytest.raises(RuntimeError):
        m.build_rate_limiter()


def test_memory_limiter_evict_after_prune_frees_space():
    """window=0 makes every hit stale, so _evict_locked's prune empties the
    map and it returns before the oldest-key eviction loop."""
    limiter = m.SlidingWindowRateLimiter(window_seconds=0.0, max_keys=1)
    limiter.check("a", 5)
    allowed, _ = limiter.check("b", 5)
    assert allowed


def test_download_registry_reset():
    reg = m.DownloadRegistry()
    reg.add(Path("tok123") / "out.bin", None)
    reg.reset()
    assert reg.resolve("tok123", None) is None


def test_download_registry_recover_rejects_escape():
    reg = m.DownloadRegistry()
    assert reg.resolve("../..", None) is None


def test_assert_single_worker_ignores_bad_count(monkeypatch):
    monkeypatch.delenv("ALLOW_MULTI_WORKER", raising=False)
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.setenv("WEB_CONCURRENCY", "abc")
    m._assert_single_worker()  # must return, not raise


def test_job_status_rejects_bad_token(auth_client):
    assert auth_client.get("/api/jobs/!!not-a-token!!").status_code == 404


# --- middleware branches --------------------------------------------------------

def test_track_uses_own_rate_limit_tier(auth_client):
    app.state.rate_limit_enabled = True
    r = auth_client.post(
        "/api/track",
        json={"event": "page_view", "label": "home", "ref": "https://example.com/x"},
    )
    assert r.status_code == 204


def test_track_invalid_json_still_204(auth_client):
    r = auth_client.post(
        "/api/track",
        content=b"{bad json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 204


def test_heavy_gate_disabled_passes_through(auth_client, monkeypatch):
    app.state.rate_limit_enabled = True
    monkeypatch.setattr(app.state, "heavy_gate", None)
    monkeypatch.setattr(m, "pdf_to_excel", _fake_tables)
    r = auth_client.post("/api/pdf/to-excel",
                         files={"file": ("doc.pdf", PDF_BYTES, "application/pdf")})
    assert r.status_code == 200


def test_content_length_malformed_and_negative():
    req = Request({
        "type": "http", "method": "POST", "path": "/api/track",
        "headers": [(b"content-length", b"abc")],
    })
    assert m._content_length(req) is None
    req2 = Request({
        "type": "http", "method": "POST", "path": "/api/track",
        "headers": [(b"content-length", b"-5")],
    })
    assert m._content_length(req2) is None


# --- housekeeping helpers -------------------------------------------------------

def test_delete_file_after_download_oserror(monkeypatch):
    def boom(*a, **k):
        raise OSError("disk gone")
    monkeypatch.setattr(m.shutil, "rmtree", boom)
    m.delete_file_after_download("tok123", Path("x") / "f.bin")  # must not raise


def test_ads_txt_unset_404(auth_client, monkeypatch):
    monkeypatch.delenv("ADSENSE_ADS_TXT", raising=False)
    assert auth_client.get("/ads.txt").status_code == 404


def test_ads_txt_set_200(auth_client, monkeypatch):
    monkeypatch.setenv("ADSENSE_ADS_TXT", "google.com, pub-1, DIRECT, f08c47fec0942fa0")
    r = auth_client.get("/ads.txt")
    assert r.status_code == 200
    assert "pub-1" in r.text


def test_build_adsense_slot_with_slot(monkeypatch):
    monkeypatch.setattr(m, "ADSENSE_CLIENT", "ca-pub-1")
    monkeypatch.setattr(m, "ADSENSE_SLOT", "123")
    html = m._build_adsense_slot()
    assert 'data-ad-slot="123"' in html
    assert 'data-ad-client="ca-pub-1"' in html


def test_build_adsense_slot_without_slot(monkeypatch):
    monkeypatch.setattr(m, "ADSENSE_CLIENT", "ca-pub-1")
    monkeypatch.setattr(m, "ADSENSE_SLOT", "")
    html = m._build_adsense_slot()
    assert "data-ad-slot" not in html


def test_build_site_verification(monkeypatch):
    monkeypatch.setattr(m, "GOOGLE_SITE_VERIFICATION", "gtoken")
    monkeypatch.setattr(m, "BING_SITE_VERIFICATION", "btoken")
    out = m._build_site_verification()
    assert "google-site-verification" in out
    assert "msvalidate.01" in out


def test_warmup_ai_success(monkeypatch):
    import scripts.ocr_engine as oe
    monkeypatch.setenv("WARMUP_AI", "1")
    monkeypatch.setattr(m, "DISABLE_AI", False)
    monkeypatch.setattr(oe, "get_ocr_engine", lambda: SimpleNamespace(name="fake"))
    asyncio.run(m._warmup_ai())


def test_warmup_ai_failure_is_swallowed(monkeypatch):
    import scripts.ocr_engine as oe
    monkeypatch.setenv("WARMUP_AI", "1")
    monkeypatch.setattr(m, "DISABLE_AI", False)
    monkeypatch.setattr(oe, "get_ocr_engine", _raiser(RuntimeError("no models")))
    asyncio.run(m._warmup_ai())  # must not raise


# --- stale-file sweeper -----------------------------------------------------------

def test_delete_stale_files_sweeps_old_entries(tmp_path):
    old = time.time() - 7200
    old_file = tmp_path / "old.bin"
    old_file.write_bytes(b"x")
    fresh_file = tmp_path / "fresh.bin"
    fresh_file.write_bytes(b"x")
    old_empty = tmp_path / "oldempty"
    old_empty.mkdir()
    old_full = tmp_path / "oldfull"
    old_full.mkdir()
    (old_full / "c.bin").write_bytes(b"x")
    fresh_dir = tmp_path / "freshdir"
    fresh_dir.mkdir()
    (fresh_dir / "c.bin").write_bytes(b"x")
    os.utime(old_file, (old, old))
    os.utime(old_empty, (old, old))
    os.utime(old_full / "c.bin", (old, old))
    os.utime(old_full, (old, old))

    m._delete_stale_files(tmp_path, ttl=60)

    assert not old_file.exists()
    assert fresh_file.exists()
    assert not old_empty.exists()
    assert not old_full.exists()
    assert fresh_dir.exists()


def test_delete_stale_files_locked_file_is_skipped(tmp_path, monkeypatch):
    old = time.time() - 7200
    old_file = tmp_path / "old.bin"
    old_file.write_bytes(b"x")
    os.utime(old_file, (old, old))

    def boom(self, *a, **k):
        raise OSError("locked")
    monkeypatch.setattr(Path, "unlink", boom)

    m._delete_stale_files(tmp_path, ttl=60)  # must not raise
    assert old_file.exists()


def test_delete_stale_files_survives_unstatable_entry():
    class BadEntry:
        def is_file(self):
            raise RuntimeError("vanished")
        def is_dir(self):
            return False

    directory = SimpleNamespace(iterdir=lambda: [BadEntry()])
    m._delete_stale_files(directory, ttl=60)  # outer except must swallow it
