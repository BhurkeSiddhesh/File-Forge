from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
import pytest
import os
import pikepdf

# Removed global client = TestClient(app)

@pytest.fixture
def mock_dirs(tmp_path):
    """Patches UPLOAD_DIR and OUTPUT_DIR to use temporary directories."""
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()

    # Patch the variables in main.py
    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield {"upload": upload_dir, "output": output_dir}

def test_read_index(auth_client):
    response = auth_client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]

def test_api_remove_password(locked_pdf, mock_dirs, auth_client):
    file_path = locked_pdf["path"]
    password = locked_pdf["password"]

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {"password": password}
        response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify file exists in mock output dir
    output_filename = data["filename"]
    assert (mock_dirs["output"] / output_filename).exists()

def test_api_remove_password_wrong_password(locked_pdf, mock_dirs, auth_client):
    file_path = locked_pdf["path"]
    wrong_password = "wrong"

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {"password": wrong_password}
        response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

    assert response.status_code == 400

def test_api_convert_to_word(sample_pdf, mock_dirs, auth_client):
    file_path = sample_pdf

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        response = auth_client.post("/api/pdf/convert-to-word", files=files)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"

    # Verify file exists in mock output dir
    output_filename = data["filename"]
    assert (mock_dirs["output"] / output_filename).exists()

def test_api_extract_pages(multi_page_pdf, mock_dirs, auth_client):
    file_path = multi_page_pdf

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {"pages": "2-3"}
        response = auth_client.post("/api/pdf/extract-pages", files=files, data=data)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["status"] == "success"
    output_filename = resp_data["filename"]
    output_path = mock_dirs["output"] / output_filename
    assert output_path.exists()

    with pikepdf.open(output_path) as pdf:
        assert len(pdf.pages) == 2

def test_download_file(sample_pdf, mock_dirs, auth_client):
    # First generate the file
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/pdf/convert-to-word", files=files)

    filename = response.json()["filename"]

    # Download it
    response = auth_client.get(f"/api/download/{filename}")
    assert response.status_code == 200
    assert response.headers["content-disposition"] == f'attachment; filename="{filename}"'

def test_download_file_not_found(mock_dirs, auth_client):
    response = auth_client.get("/api/download/nonexistent.file")
    assert response.status_code == 404


def test_api_heic_to_jpeg(sample_heic, mock_dirs, auth_client):
    """Test HEIC to JPEG conversion endpoint."""
    file_path = sample_heic

    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "image/heic")}
        data = {"quality": 90}
        response = auth_client.post("/api/image/heic-to-jpeg", files=files, data=data)

    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "success"
    assert data["filename"].endswith(".jpg")

    # Verify file exists in mock output dir
    output_filename = data["filename"]
    assert (mock_dirs["output"] / output_filename).exists()


def test_api_resize_image(sample_image_file, mock_dirs, auth_client):
    """Test image resizing endpoint."""
    with open(sample_image_file, "rb") as f:
        files = {"file": (sample_image_file.name, f, "image/jpeg")}
        data = {"mode": "dimensions", "width": 50, "height": 50}
        response = auth_client.post("/api/image/resize", files=files, data=data)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["status"] == "success"
    assert "resized" in resp_data["filename"]
    assert (mock_dirs["output"] / resp_data["filename"]).exists()


def test_api_crop_image(sample_image_file, mock_dirs, auth_client):
    """Test image cropping endpoint."""
    with open(sample_image_file, "rb") as f:
        files = {"file": (sample_image_file.name, f, "image/jpeg")}
        data = {"x": 10, "y": 10, "width": 30, "height": 30}
        response = auth_client.post("/api/image/crop", files=files, data=data)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["status"] == "success"
    assert "cropped" in resp_data["filename"]
    assert (mock_dirs["output"] / resp_data["filename"]).exists()

def test_download_file_deletes_after_download(sample_pdf, mock_dirs, auth_client) -> None:
    """
    Verifies that a file is successfully served and then automatically deleted
    from the output directory after download.
    """
    # First generate the file
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        response = auth_client.post("/api/pdf/convert-to-word", files=files)
    
    assert response.status_code == 200
    filename = response.json()["filename"]
    file_path = mock_dirs["output"] / filename

    assert file_path.exists()

    # Download it
    response = auth_client.get(f"/api/download/{filename}")
    assert response.status_code == 200

    # Check if the file is deleted
    assert not file_path.exists()


# ---------------------------------------------------------------------------
# /api/pdf/compress endpoint tests
# ---------------------------------------------------------------------------

def test_api_compress_pdf(sample_pdf, mock_dirs, auth_client):
    """Compress endpoint returns success and size statistics."""
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"level": "low"}
        response = auth_client.post("/api/pdf/compress", files=files, data=data)

    assert response.status_code == 200
    resp_data = response.json()
    assert resp_data["status"] == "success"
    assert "filename" in resp_data
    assert "original_size" in resp_data
    assert "compressed_size" in resp_data
    assert "reduction_pct" in resp_data
    assert (mock_dirs["output"] / resp_data["filename"]).exists()


def test_api_compress_pdf_medium_level(sample_pdf, mock_dirs, auth_client):
    """Compress endpoint works with level='medium'."""
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"level": "medium"}
        response = auth_client.post("/api/pdf/compress", files=files, data=data)

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_api_compress_pdf_requires_auth(sample_pdf, mock_dirs):
    """Compress endpoint requires authentication."""
    from fastapi.testclient import TestClient
    unauth_client = TestClient(app)
    with patch("main.UPLOAD_DIR", mock_dirs["upload"]), patch("main.OUTPUT_DIR", mock_dirs["output"]):
        with open(sample_pdf, "rb") as f:
            files = {"file": (sample_pdf.name, f, "application/pdf")}
            response = unauth_client.post("/api/pdf/compress", files=files, data={"level": "low"})
    assert response.status_code == 403


def test_api_compress_pdf_with_password(locked_pdf, mock_dirs, auth_client):
    """Compress endpoint decrypts and compresses a password-protected PDF."""
    file_path = locked_pdf["path"]
    password = locked_pdf["password"]
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {"level": "low", "password": password}
        response = auth_client.post("/api/pdf/compress", files=files, data=data)

    assert response.status_code == 200
    assert response.json()["status"] == "success"


def test_api_compress_pdf_path_traversal_sanitized(sample_pdf, mock_dirs, auth_client):
    """Filename with path traversal components is sanitized before saving."""
    with open(sample_pdf, "rb") as f:
        files = {"file": ("../../evil.pdf", f, "application/pdf")}
        data = {"level": "low"}
        response = auth_client.post("/api/pdf/compress", files=files, data=data)

    assert response.status_code == 200
    filename = response.json()["filename"]
    # Should not contain directory separators
    assert "/" not in filename
    assert "\\" not in filename


# ---------------------------------------------------------------------------
# /api/workflow/execute endpoint tests
# ---------------------------------------------------------------------------

def test_api_workflow_invalid_steps_json(sample_pdf, mock_dirs, auth_client):
    """Workflow endpoint returns 400 for invalid JSON in steps field."""
    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"steps": "not valid json"}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 400


def test_api_workflow_single_pdf_to_word_step(sample_pdf, mock_dirs, auth_client):
    """Workflow with a single pdf_to_word step streams events and completes."""
    import json

    steps = json.dumps([{"type": "pdf_to_word", "config": {"use_ai": False}, "label": "Convert to Word"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"steps": steps}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 200
    # SSE response — check that a 'complete' event is present in the body
    body = response.text
    assert "complete" in body


def test_api_workflow_unknown_step_type(sample_pdf, mock_dirs, auth_client):
    """Workflow with an unknown step type sends an error event."""
    import json

    steps = json.dumps([{"type": "does_not_exist", "config": {}}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"steps": steps}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 200
    body = response.text
    assert "error" in body


def test_api_workflow_compress_step(sample_pdf, mock_dirs, auth_client):
    """Workflow with a compress_pdf step completes successfully."""
    import json

    steps = json.dumps([{"type": "compress_pdf", "config": {"level": "low"}, "label": "Compress"}])

    with open(sample_pdf, "rb") as f:
        files = {"file": (sample_pdf.name, f, "application/pdf")}
        data = {"steps": steps}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 200
    assert "complete" in response.text


def test_api_workflow_resize_image_step(sample_image_file, mock_dirs, auth_client):
    """Workflow with a resize_image step completes successfully."""
    import json

    steps = json.dumps([{"type": "resize_image", "config": {"mode": "percentage", "percentage": 50}}])

    with open(sample_image_file, "rb") as f:
        files = {"file": (sample_image_file.name, f, "image/jpeg")}
        data = {"steps": steps}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 200
    assert "complete" in response.text


def test_api_workflow_crop_image_step(sample_image_file, mock_dirs, auth_client):
    """Workflow with a crop_image step completes successfully."""
    import json

    steps = json.dumps([{"type": "crop_image", "config": {"x": 0, "y": 0, "width": 50, "height": 50}}])

    with open(sample_image_file, "rb") as f:
        files = {"file": (sample_image_file.name, f, "image/jpeg")}
        data = {"steps": steps}
        response = auth_client.post("/api/workflow/execute", files=files, data=data)

    assert response.status_code == 200
    assert "complete" in response.text


# ---------------------------------------------------------------------------
# delete_file_after_download unit tests
# ---------------------------------------------------------------------------

def test_delete_file_after_download_removes_file(tmp_path):
    """delete_file_after_download removes an existing file."""
    from main import delete_file_after_download
    test_file = tmp_path / "to_delete.txt"
    test_file.write_text("hello")

    delete_file_after_download(test_file)

    assert not test_file.exists()


def test_delete_file_after_download_missing_file_is_silent(tmp_path):
    """delete_file_after_download does not raise when file does not exist."""
    from main import delete_file_after_download
    missing = tmp_path / "nonexistent.txt"

    # Should not raise
    delete_file_after_download(missing)


# ---------------------------------------------------------------------------
# Path traversal sanitization for other endpoints
# ---------------------------------------------------------------------------

def test_api_remove_password_path_traversal_sanitized(locked_pdf, mock_dirs, auth_client):
    """Path traversal in filename is sanitized for remove-password endpoint."""
    file_path = locked_pdf["path"]
    password = locked_pdf["password"]

    with open(file_path, "rb") as f:
        files = {"file": ("../../evil.pdf", f, "application/pdf")}
        data = {"password": password}
        response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

    assert response.status_code == 200
    filename = response.json()["filename"]
    assert "/" not in filename
    assert "\\" not in filename
