"""Tests for input validation on numeric parameters (Issue #45)."""
import io
import pytest
from PIL import Image


def _image_payload():
    buf = io.BytesIO()
    Image.new("RGB", (50, 50), color="red").save(buf, "JPEG")
    buf.seek(0)
    return {"file": ("test.jpg", buf, "image/jpeg")}


class TestResizeValidation:
    def test_invalid_mode_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/resize",
            files=_image_payload(),
            data={"mode": "bogus"},
        )
        assert resp.status_code == 422
        assert "mode" in resp.json()["detail"]

    def test_zero_width_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/resize",
            files=_image_payload(),
            data={"mode": "dimensions", "width": "0"},
        )
        assert resp.status_code == 422
        assert "width" in resp.json()["detail"]

    def test_negative_percentage_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/resize",
            files=_image_payload(),
            data={"mode": "percentage", "percentage": "-5"},
        )
        assert resp.status_code == 422

    def test_percentage_over_limit_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/resize",
            files=_image_payload(),
            data={"mode": "percentage", "percentage": "501"},
        )
        assert resp.status_code == 422

    def test_valid_percentage_accepted(self, auth_client):
        resp = auth_client.post(
            "/api/image/resize",
            files=_image_payload(),
            data={"mode": "percentage", "percentage": "50"},
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "success"


class TestCropValidation:
    def test_negative_origin_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/crop",
            files=_image_payload(),
            data={"x": "-1", "y": "0", "width": "10", "height": "10"},
        )
        assert resp.status_code == 422

    def test_zero_dimensions_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/crop",
            files=_image_payload(),
            data={"x": "0", "y": "0", "width": "0", "height": "10"},
        )
        assert resp.status_code == 422

    def test_valid_crop_accepted(self, auth_client):
        resp = auth_client.post(
            "/api/image/crop",
            files=_image_payload(),
            data={"x": "0", "y": "0", "width": "10", "height": "10"},
        )
        assert resp.status_code == 200


class TestQualityValidation:
    @pytest.mark.parametrize("endpoint,extra", [
        ("/api/image/compress", {}),
        ("/api/image/rotate", {"angle": "90"}),
        ("/api/image/convert", {"target_format": "png"}),
        ("/api/image/heic-to-jpeg", {}),
    ])
    def test_quality_out_of_range_rejected(self, auth_client, endpoint, extra):
        for bad_quality in ("0", "999", "-3"):
            resp = auth_client.post(
                endpoint,
                files=_image_payload(),
                data={**extra, "quality": bad_quality},
            )
            assert resp.status_code == 422, f"{endpoint} accepted quality={bad_quality}"

    def test_valid_quality_accepted(self, auth_client):
        resp = auth_client.post(
            "/api/image/compress",
            files=_image_payload(),
            data={"quality": "70"},
        )
        assert resp.status_code == 200


class TestWatermarkOpacityValidation:
    def test_opacity_above_one_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/watermark",
            files=_image_payload(),
            data={"text": "TEST", "opacity": "1.5"},
        )
        assert resp.status_code == 422

    def test_negative_opacity_rejected(self, auth_client):
        resp = auth_client.post(
            "/api/image/watermark",
            files=_image_payload(),
            data={"text": "TEST", "opacity": "-0.1"},
        )
        assert resp.status_code == 422


# ---------------------------------------------------------------------------
# Whole-API upload intake sweep (issue #8)
#
# MAX_UPLOAD_MB and the extension allowlist used to be enforced by save_upload()
# on exactly one of 34 upload handlers; the other 33 inlined an unbounded
# shutil.copyfileobj(). These tests walk every POST route that declares an
# UploadFile and assert both gates fire, so an endpoint added later cannot
# quietly skip the helper.
# ---------------------------------------------------------------------------
import inspect

from fastapi import UploadFile
from fastapi.params import File as _FileParam, Form as _FormParam
from fastapi.routing import APIRoute

import main as _main


# Plausible values for each *required* Form field, so the request reaches the
# upload intake instead of being turned away as a 422 by request validation.
# A new endpoint with a new required field lands here.
_FORM_SAMPLES = {
    "mode": "percentage",
    "password": "pw",
    "user_password": "pw",
    "owner_password": "pw",
    "pages": "1",
    "page_order": "1",
    "angle": "90",
    "annotations": "[]",
    "text": "watermark",
    "steps": '[{"type": "rotate_pdf", "config": {"angle": 90}}]',
}


def _is_required(param_default):
    """True when a Form(...) field has no default.

    FastAPI normalises the `...` sentinel to pydantic's PydanticUndefined, so
    an `is Ellipsis` check silently matches nothing and every route then 422s.
    """
    is_required = getattr(param_default, "is_required", None)
    if callable(is_required):
        return is_required()
    return param_default.default is Ellipsis


def _sample_for(name, annotation):
    if name in _FORM_SAMPLES:
        return _FORM_SAMPLES[name]
    if annotation is int:
        return "1"
    if annotation is float:
        return "1.0"
    if annotation is bool:
        return "false"
    return "x"


def _upload_routes():
    """Every POST route taking an UploadFile, as (path, file_fields, form_data)."""
    found = []
    for route in _main.app.routes:
        if not isinstance(route, APIRoute) or "POST" not in route.methods:
            continue
        file_fields, form_data = {}, {}
        for name, param in inspect.signature(route.endpoint).parameters.items():
            default, annotation = param.default, param.annotation
            if isinstance(default, _FileParam):
                # List[UploadFile] endpoints require at least two files.
                file_fields[name] = getattr(annotation, "__origin__", None) is list
            elif isinstance(default, _FormParam) and _is_required(default):
                form_data[name] = _sample_for(name, annotation)
        if file_fields:
            found.append((route.path, file_fields, form_data))
    return sorted(found)


UPLOAD_ROUTES = _upload_routes()


# The extension gate runs before the size gate, so the oversize case has to send
# a name the route's own allowlist accepts or it 415s before reaching the cap.
_FAMILY_NAMES = {
    "/api/image/": "sample.png",
    "/api/excel/": "sample.xlsx",
    "/api/ppt/": "sample.pptx",
    "/api/word/": "sample.docx",
}


def _accepted_name(path):
    for prefix, name in _FAMILY_NAMES.items():
        if path.startswith(prefix):
            return name
    return "sample.pdf"


def _payload(file_fields, filename, content):
    """multipart file list; list-valued fields get two entries."""
    files = []
    for field, is_list in file_fields.items():
        # /api/pdf/sign gates the signature on Content-Type before intake runs.
        ctype = "image/png" if field == "signature" else "application/octet-stream"
        entry = (field, (filename, content, ctype))
        files.append(entry)
        if is_list:
            files.append(entry)
    return files


def test_sweep_covers_the_whole_upload_surface():
    """Guard the guard: if this collapses to a handful, the sweep stopped working."""
    assert len(UPLOAD_ROUTES) >= 30, UPLOAD_ROUTES


@pytest.mark.parametrize("path,file_fields,form_data", UPLOAD_ROUTES,
                         ids=[r[0] for r in UPLOAD_ROUTES])
def test_every_upload_endpoint_enforces_the_size_cap(
    path, file_fields, form_data, auth_client, monkeypatch, tmp_path
):
    monkeypatch.setattr(_main, "UPLOAD_DIR", tmp_path)
    monkeypatch.setattr(_main, "MAX_UPLOAD_MB", 0)  # any non-empty body is oversize
    resp = auth_client.post(
        path,
        files=_payload(file_fields, _accepted_name(path), b"x" * 4096),
        data=form_data,
    )
    assert resp.status_code == 413, (
        f"{path} returned {resp.status_code}, not 413 — it is probably writing the "
        f"upload itself instead of going through save_upload()/save_uploads(). "
        f"(A 422 here means _FORM_SAMPLES is missing one of its required fields.)"
    )
    assert list(tmp_path.iterdir()) == [], f"{path} left an oversized upload on disk"


@pytest.mark.parametrize("path,file_fields,form_data", UPLOAD_ROUTES,
                         ids=[r[0] for r in UPLOAD_ROUTES])
def test_every_upload_endpoint_enforces_the_extension_allowlist(
    path, file_fields, form_data, auth_client, monkeypatch, tmp_path
):
    monkeypatch.setattr(_main, "UPLOAD_DIR", tmp_path)
    resp = auth_client.post(
        path,
        files=_payload(file_fields, "evil.exe", b"MZ\x90\x00"),
        data=form_data,
    )
    assert resp.status_code == 415, (
        f"{path} returned {resp.status_code}, not 415 — an unsupported type reached "
        f"the parser. (A 422 here means _FORM_SAMPLES is missing a required field.)"
    )
    assert list(tmp_path.iterdir()) == [], f"{path} left a rejected upload on disk"
