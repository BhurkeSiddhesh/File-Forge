from unittest.mock import patch, MagicMock
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

    # We mock shutil.copyfileobj to intercept the file write
    with patch("main.shutil.copyfileobj") as mock_copy:
        # Mock the processing function to avoid actual PDF processing
        with patch.object(main, "remove_pdf_password") as mock_remove:
            mock_remove.return_value = "output.pdf"

            files = {"file": ("test.pdf", b"dummy content", "application/pdf")}
            data = {"password": "pass"}

            response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

            assert response.status_code == 200

            # Check copyfileobj calls
            assert mock_copy.called
            args, _ = mock_copy.call_args
            dest_buffer = args[1]
            dest_path = dest_buffer.name

            print(f"Destination path: {dest_path}")

            filename = Path(dest_path).name

            # Security check: filename should NOT be exactly "test.pdf"
            # It should be randomized (e.g. UUID_test.pdf)
            if filename == "test.pdf":
                pytest.fail(f"VULNERABILITY DETECTED: Uploaded file saved as '{filename}' without randomization.")

            assert "test.pdf" in filename
            # UUID is 36 chars. + 1 underscore + 8 chars for "test.pdf" = 45 chars approx.
            assert len(filename) > 36
