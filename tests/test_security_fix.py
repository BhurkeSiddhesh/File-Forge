import re
from unittest.mock import patch
from fastapi.testclient import TestClient
from main import app
import pytest
from pathlib import Path

client = TestClient(app)

@pytest.fixture
def mock_dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield upload_dir, output_dir

import main

_UUID_PREFIX_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}_'
)


def test_upload_filename_is_unique(mock_dirs, auth_client):
    """Uploads land under '<uuid4>_<sanitized original>'.

    The original name is deliberately *kept* (scripts/utils.original_stem strips
    the prefix back off so the download is named after what the user sent). The
    security property is the unique prefix — it makes the path unguessable and
    collision-free — not the erasure of the name.
    """
    upload_dir, _ = mock_dirs

    saved_paths = []
    real_save_upload = main.save_upload

    def spy_save_upload(file, allowed=None):
        dest = real_save_upload(file, allowed)
        saved_paths.append(dest)
        return dest

    with patch.object(main, "save_upload", side_effect=spy_save_upload):
        # Mock the processing function to avoid actual PDF processing
        with patch.object(main, "remove_pdf_password") as mock_remove:
            mock_remove.return_value = "output.pdf"

            files = {"file": ("test.pdf", b"dummy content", "application/pdf")}
            data = {"password": "pass"}

            response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

            assert response.status_code == 200
            assert saved_paths, "save_upload was not called"

            filename = Path(saved_paths[0]).name

            if filename == "test.pdf":
                pytest.fail(f"VULNERABILITY DETECTED: Uploaded file saved as '{filename}' without randomization.")

            assert _UUID_PREFIX_RE.match(filename), filename
            # ...and the original name survives behind the prefix, which is what
            # keeps the user's download from being named after a UUID (issue #12).
            assert filename.endswith("_test.pdf")


def test_two_uploads_of_the_same_name_do_not_collide(mock_dirs, auth_client):
    """Concurrent users converting identically-named files get separate paths."""
    saved_paths = []
    real_save_upload = main.save_upload

    def spy_save_upload(file, allowed=None):
        dest = real_save_upload(file, allowed)
        saved_paths.append(dest)
        return dest

    with patch.object(main, "save_upload", side_effect=spy_save_upload):
        with patch.object(main, "remove_pdf_password") as mock_remove:
            mock_remove.return_value = "output.pdf"
            for _ in range(2):
                auth_client.post(
                    "/api/pdf/remove-password",
                    files={"file": ("report.pdf", b"dummy content", "application/pdf")},
                    data={"password": "pass"},
                )

    assert len(saved_paths) == 2
    assert saved_paths[0] != saved_paths[1]


def test_upload_size_cap_enforced(mock_dirs, auth_client, monkeypatch):
    """Uploads over MAX_UPLOAD_MB are rejected with 413 and nothing is left on disk."""
    upload_dir, _ = mock_dirs
    monkeypatch.setattr(main, "MAX_UPLOAD_MB", 1)

    big_payload = b"x" * (2 * 1024 * 1024)  # 2 MB > 1 MB cap
    files = {"file": ("big.pdf", big_payload, "application/pdf")}
    response = auth_client.post("/api/pdf/remove-password", files=files, data={"password": "p"})

    assert response.status_code == 413
    assert list(upload_dir.iterdir()) == [], "oversized upload must not remain on disk"


def test_extract_pages_path_traversal_sanitized(mock_dirs, auth_client, multi_page_pdf):
    """extract-pages previously saved uploads under the raw client filename."""
    upload_dir, _ = mock_dirs
    with open(multi_page_pdf, "rb") as f:
        files = {"file": ("../../evil.pdf", f, "application/pdf")}
        response = auth_client.post("/api/pdf/extract-pages", files=files, data={"pages": "1"})

    assert response.status_code == 200
    filename = response.json()["filename"]
    assert "/" not in filename and "\\" not in filename
    # Nothing escaped the upload dir
    assert not (upload_dir.parent / "evil.pdf").exists()


# ---------------------------------------------------------------------------
# Download authorization (issue #5)
#
# Output names are deterministic — branded_filename() maps every "resume.pdf"
# to "resume_forgefiles.org.pdf" — and /api/download used to serve them out of
# one flat directory with no ownership check, so polling guessable names
# harvested other visitors' documents. Results now live in a per-result
# directory named by an unguessable token, and only that token addresses them.
# ---------------------------------------------------------------------------

def _convert(client, name="resume.pdf"):
    """Run a cheap conversion and return the response payload."""
    import io
    from reportlab.pdfgen import canvas

    buf = io.BytesIO()
    c = canvas.Canvas(buf)
    c.drawString(100, 750, "hello")
    c.save()
    buf.seek(0)
    resp = client.post(
        "/api/pdf/rotate",
        files={"file": (name, buf, "application/pdf")},
        data={"angle": "90"},
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


def test_branded_filename_is_not_a_download_key(mock_dirs, auth_client):
    """The old attack: guess the output name, fetch the stranger's file."""
    payload = _convert(auth_client, "resume.pdf")
    assert payload["filename"] == "resume_forgefiles.org.pdf"

    # A second visitor guesses the (entirely predictable) name.
    stranger = TestClient(app)
    assert stranger.get("/api/download/resume_forgefiles.org.pdf").status_code == 404

    # And the real owner's token still works.
    assert auth_client.get(f"/api/download/{payload['download_token']}").status_code == 200


def test_concurrent_same_name_conversions_do_not_collide(mock_dirs, auth_client):
    """Two people converting 'report.pdf' must not share an output path."""
    first = _convert(auth_client, "report.pdf")
    second = _convert(TestClient(app), "report.pdf")

    assert first["filename"] == second["filename"] == "report_forgefiles.org.pdf"
    assert first["download_token"] != second["download_token"]

    first_path = main.app.state.downloads.resolve(first["download_token"], None)
    second_path = main.app.state.downloads.resolve(second["download_token"], None)
    assert first_path != second_path
    assert first_path.exists() and second_path.exists()

    # Downloading one must not consume the other.
    assert auth_client.get(f"/api/download/{first['download_token']}").status_code == 200
    assert second_path.exists()


def test_token_from_another_session_is_rejected_when_bound(mock_dirs, auth_client, monkeypatch):
    """With DOWNLOAD_BIND_SESSION on, a leaked token is useless elsewhere."""
    monkeypatch.setattr(main, "DOWNLOAD_BIND_SESSION", True)

    payload = _convert(auth_client, "payslip.pdf")
    token = payload["download_token"]

    # A different client carries a different ff_sid.
    other_session = TestClient(app)
    other_session.get("/api/ai-capabilities")  # pick up its own session cookie
    assert other_session.get(f"/api/download/{token}").status_code == 404

    # The originating session is unaffected.
    assert auth_client.get(f"/api/download/{token}").status_code == 200


def test_download_rejects_malformed_tokens(auth_client):
    for bogus in ("../../etc/passwd", "..%2f..%2fetc%2fpasswd", "short", "a" * 200):
        resp = auth_client.get(f"/api/download/{bogus}")
        assert resp.status_code == 404, bogus
