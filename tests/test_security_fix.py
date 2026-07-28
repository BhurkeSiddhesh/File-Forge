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
