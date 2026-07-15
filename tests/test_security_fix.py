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

def test_upload_filename_is_unique(mock_dirs, auth_client):
    upload_dir, _ = mock_dirs

    saved_paths = []
    real_save_upload = main.save_upload

    def spy_save_upload(file):
        dest = real_save_upload(file)
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

            # Security check: filename should NOT be exactly "test.pdf"
            # It should be purely a UUID + .pdf
            if filename == "test.pdf":
                pytest.fail(f"VULNERABILITY DETECTED: Uploaded file saved as '{filename}' without randomization.")

            assert "test.pdf" not in filename
            # UUID hex is 32 chars, plus ".pdf" = 36 chars.
            assert len(filename) >= 36


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
