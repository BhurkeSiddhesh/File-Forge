import pytest
from pathlib import Path
from reportlab.pdfgen import canvas
import pikepdf

@pytest.fixture(scope="session")
def sample_pdf(tmp_path_factory):
    """Creates a simple PDF file for testing."""
    # Create a temporary directory for the session
    d = tmp_path_factory.mktemp("data")
    file_path = d / "sample.pdf"

    # Generate PDF using ReportLab
    c = canvas.Canvas(str(file_path))
    c.drawString(100, 750, "Hello, this is a test PDF.")
    c.save()

    return file_path

@pytest.fixture(scope="session")
def multi_page_pdf(tmp_path_factory):
    """Creates a multi-page PDF file for extraction tests."""
    d = tmp_path_factory.mktemp("multi_data")
    file_path = d / "multi_sample.pdf"

    c = canvas.Canvas(str(file_path))
    for i in range(1, 5):
        c.drawString(100, 750, f"Page {i}")
        c.showPage()
    c.save()

    return file_path

@pytest.fixture(scope="session")
def locked_pdf(tmp_path_factory, sample_pdf):
    """Creates a password-protected PDF file."""
    d = tmp_path_factory.mktemp("locked_data")
    file_path = d / "locked.pdf"
    password = "secret_password"

    with pikepdf.open(sample_pdf) as pdf:
        # Encrypt the PDF
        pdf.save(
            file_path,
            encryption=pikepdf.Encryption(
                user=password,
                owner=password
            )
        )

    return {"path": file_path, "password": password}


@pytest.fixture(scope="session")
def sample_heic(tmp_path_factory):
    """Creates a sample HEIC file for testing."""
    try:
        import pillow_heif
        from PIL import Image
        
        pillow_heif.register_heif_opener()
        
        d = tmp_path_factory.mktemp("images")
        file_path = d / "test_image.heic"
        
        # Create a simple RGB image and save as HEIC
        img = Image.new('RGB', (100, 100), color='blue')
        img.save(file_path, format='HEIF')
        
        return file_path
    except Exception as e:
        pytest.skip(f"Could not create test HEIC: {e}")

@pytest.fixture(scope="session")
def sample_image_file(tmp_path_factory):
    """Creates a sample JPEG image for testing."""
    d = tmp_path_factory.mktemp("img_gen")
    file_path = d / "test.jpg"
    from PIL import Image
    img = Image.new('RGB', (100, 100), color='green')
    img.save(file_path, "JPEG")
    return file_path

# Auth Fixtures
from main import app
from fastapi.testclient import TestClient
import os

@pytest.fixture(autouse=True)
def mock_auth():
    """Sets a known API key for testing."""
    test_key = "test-secret-key"
    app.state.api_key = test_key
    os.environ["FILE_FORGE_API_KEY"] = test_key
    yield test_key

@pytest.fixture
def auth_client(mock_auth):
    """Returns a TestClient with authentication headers."""
    client = TestClient(app)
    client.headers = {"X-API-Key": mock_auth}
    return client
