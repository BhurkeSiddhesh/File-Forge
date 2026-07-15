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
