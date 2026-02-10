from fastapi.testclient import TestClient
from main import app
import pytest

@pytest.fixture
def unauth_client():
    return TestClient(app)

def test_api_no_auth(unauth_client):
    """Test accessing sensitive endpoint without API Key."""
    response = unauth_client.post("/api/pdf/remove-password", data={})
    assert response.status_code == 403
    assert response.json()["detail"] == "Could not validate credentials"

def test_api_wrong_auth(unauth_client):
    """Test accessing sensitive endpoint with WRONG API Key."""
    response = unauth_client.post(
        "/api/pdf/remove-password",
        headers={"X-API-Key": "wrong-key"},
        data={}
    )
    assert response.status_code == 403

def test_api_correct_auth(auth_client, locked_pdf):
    """Test accessing sensitive endpoint with CORRECT API Key."""
    file_path = locked_pdf["path"]
    with open(file_path, "rb") as f:
        files = {"file": (file_path.name, f, "application/pdf")}
        data = {"password": "wrong"}
        response = auth_client.post("/api/pdf/remove-password", files=files, data=data)

    # Should not be 403
    assert response.status_code != 403
    assert response.status_code in [200, 400]

def test_download_query_param_auth(mock_auth):
    """Test accessing download endpoint with query param auth."""
    client = TestClient(app)

    # Without key -> 403
    response = client.get("/api/download/test.txt")
    assert response.status_code == 403

    # With correct query param -> 404 (file not found) means auth passed
    response = client.get(f"/api/download/test.txt?api_key={mock_auth}")
    assert response.status_code == 404
