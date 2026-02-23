from fastapi.testclient import TestClient
from main import app
from unittest.mock import patch
import pytest
import os

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
