"""Tests for backend GA4 Measurement Protocol client (ga4_mp.py)."""
import json
from unittest.mock import AsyncMock, MagicMock, patch
import pytest

from fastapi.testclient import TestClient
import httpx

from scripts import ga4_mp, event_log
from scripts.ga4_mp import (
    build_mp_payload,
    classify_error,
    classify_error_category,
    extract_client_id,
    extract_client_id_from_cookie,
    extract_client_id_from_header,
    get_api_secret,
    get_measurement_id,
    get_request_client_id,
    infer_file_type_from_operation,
    is_enabled,
    is_ga4_mp_enabled,
    reset_request_client_id,
    send_ga4_mp_event,
    send_processing_completed,
    send_processing_failed,
    send_processing_started,
    set_request_client_id,
    validate_client_id,
    _dispatch_http,
)
import main
from main import app


@pytest.fixture
def client():
    return TestClient(app)


# --- 1. Environment Gating & is_enabled ---

def test_is_disabled_by_default(monkeypatch):
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ANALYTICS_ID", raising=False)
    monkeypatch.delenv("GA_API_SECRET", raising=False)
    assert not is_ga4_mp_enabled()
    assert not is_enabled()


def test_is_disabled_when_secret_missing(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.delenv("GA_API_SECRET", raising=False)
    assert not is_ga4_mp_enabled()


def test_is_disabled_when_measurement_id_missing(monkeypatch):
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("GOOGLE_ANALYTICS_ID", raising=False)
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    assert not is_ga4_mp_enabled()


def test_is_disabled_when_measurement_id_malformed(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "INVALID_ID")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    assert not is_ga4_mp_enabled()


def test_is_enabled_when_both_present_and_valid(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    assert is_ga4_mp_enabled()
    assert is_enabled()
    assert get_measurement_id() == "G-TEST12345"
    assert get_api_secret() == "test_secret_123"


# --- 2. Client ID Validation & Extraction ---

def test_extract_client_id_from_cookie():
    assert extract_client_id_from_cookie("1234567890.1700000000") == "1234567890.1700000000"
    assert extract_client_id_from_cookie("GA1.1.1234567890.1700000000") == "1234567890.1700000000"
    assert extract_client_id_from_cookie("GA1.2.987654321.123456789") == "987654321.123456789"


def test_extract_client_id_from_header():
    assert extract_client_id_from_header("1234567890.1700000000") == "1234567890.1700000000"
    assert extract_client_id_from_header("987654321.123456789") == "987654321.123456789"


def test_validate_client_id_rejection_and_privacy():
    # Rejects emails, paths, HTML tags, empty strings, None
    assert validate_client_id("admin@forgefiles.org") is None
    assert validate_client_id("../../../etc/passwd") is None
    assert validate_client_id("<script>alert(1)</script>") is None
    assert validate_client_id("") is None
    assert validate_client_id(None) is None


def test_extract_client_id_from_request():
    # Mock request with cookies
    req_cookie = MagicMock()
    req_cookie.cookies = {"_ga": "GA1.1.1234567890.1700000000"}
    req_cookie.headers = {}
    assert extract_client_id(req_cookie) == "1234567890.1700000000"

    # Mock request with header
    req_header = MagicMock()
    req_header.cookies = {}
    req_header.headers = {"x-ga-client-id": "987654321.123456789"}
    assert extract_client_id(req_header) == "987654321.123456789"

    # Empty request
    assert extract_client_id(None) is None


# --- 3. Error Classification ---

def test_classify_error_categories():
    assert classify_error_category("Password protected PDF") == "invalid_file"
    assert classify_error_category("File is corrupted") == "invalid_file"
    assert classify_error_category("Operation timed out after 30s") == "timeout"
    assert classify_error_category("LibreOffice executable failed") == "libreoffice"
    assert classify_error_category("PaddleOCR recognition failed") == "ocr"
    assert classify_error_category("Unsupported file format") == "unsupported_file"
    assert classify_error_category("Client cancelled conversion") == "cancelled"
    assert classify_error_category("Rate limit exceeded 429") == "rate_limited"
    assert classify_error_category("HTTP 500 internal server error") == "server_error"
    assert classify_error_category("Some random exception") == "conversion_error"
    assert classify_error_category(None) == "conversion_error"

    # HTTP Status code classification
    assert classify_error(408) == "timeout"
    assert classify_error(413) == "unsupported_file"
    assert classify_error(400) == "invalid_file"
    assert classify_error(429) == "rate_limited"
    assert classify_error(499) == "cancelled"
    assert classify_error(500) == "server_error"


# --- 4. ContextVar Management ---

def test_contextvar_lifecycle():
    assert get_request_client_id() is None
    token = set_request_client_id("1234567890.1700000000")
    assert get_request_client_id() == "1234567890.1700000000"
    reset_request_client_id(token)
    assert get_request_client_id() is None


# --- 5. Payload Building & Schema Compliance ---

def test_build_mp_payload():
    payload = build_mp_payload(
        event_name="processing_completed",
        params={
            "tool_name": "merge_pdf",
            "file_type": "pdf",
            "processing_duration_ms": 350.5,
            # Forbidden / sensitive parameters that must be dropped:
            "filename": "confidential_document.pdf",
            "email": "user@example.com",
            "user_id": "usr_9999",
        },
        client_id="1234567890.1700000000",
    )

    assert payload["client_id"] == "1234567890.1700000000"
    assert len(payload["events"]) == 1
    event = payload["events"][0]
    assert event["name"] == "processing_completed"
    assert event["params"]["tool_name"] == "merge_pdf"
    assert event["params"]["file_type"] == "pdf"
    assert event["params"]["processing_duration_ms"] == 350

    # Strictly verify stripped parameters
    assert "filename" not in event["params"]
    assert "email" not in event["params"]
    assert "user_id" not in event["params"]


# --- 6. Non-blocking Dispatch & Suppression ---

def test_send_skipped_when_disabled(monkeypatch):
    monkeypatch.delenv("GA_MEASUREMENT_ID", raising=False)
    monkeypatch.delenv("GA_API_SECRET", raising=False)
    with patch("scripts.ga4_mp._dispatch_http") as mock_http:
        send_processing_started(operation="merge_pdf", client_id="1234567890.1700000000")
        send_processing_completed(operation="merge_pdf", duration_ms=120, client_id="1234567890.1700000000")
        send_processing_failed(operation="merge_pdf", error="error", client_id="1234567890.1700000000")
        mock_http.assert_not_called()


def test_send_skipped_when_no_client_id(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    with patch("scripts.ga4_mp._dispatch_http") as mock_http:
        send_processing_started(operation="merge_pdf", client_id=None)
        send_processing_completed(operation="merge_pdf", duration_ms=120, client_id=None)
        send_processing_failed(operation="merge_pdf", error="error", client_id=None)
        mock_http.assert_not_called()


def test_send_processing_started_payload(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    dispatched = []

    def fake_send(event_name, params, client_id=None):
        dispatched.append({"event_name": event_name, "params": params, "client_id": client_id})

    with patch("scripts.ga4_mp.send_ga4_mp_event", side_effect=fake_send):
        send_processing_started(operation="compress_pdf", client_id="1234567890.1700000000")

    assert len(dispatched) == 1
    d = dispatched[0]
    assert d["event_name"] == "processing_started"
    assert d["params"]["tool_name"] == "compress_pdf"
    assert d["params"]["file_type"] == "pdf"
    assert d["client_id"] == "1234567890.1700000000"


def test_send_processing_completed_payload(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    dispatched = []

    def fake_send(event_name, params, client_id=None):
        dispatched.append({"event_name": event_name, "params": params, "client_id": client_id})

    with patch("scripts.ga4_mp.send_ga4_mp_event", side_effect=fake_send):
        send_processing_completed(
            operation="merge_pdf",
            duration_ms=450.7,
            client_id="1234567890.1700000000",
        )

    assert len(dispatched) == 1
    d = dispatched[0]
    assert d["event_name"] == "processing_completed"
    assert d["params"]["tool_name"] == "merge_pdf"
    assert d["params"]["file_type"] == "pdf"
    assert d["params"]["processing_duration_ms"] == 450.7
    assert d["client_id"] == "1234567890.1700000000"


def test_send_processing_failed_payload(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")
    dispatched = []

    def fake_send(event_name, params, client_id=None):
        dispatched.append({"event_name": event_name, "params": params, "client_id": client_id})

    with patch("scripts.ga4_mp.send_ga4_mp_event", side_effect=fake_send):
        send_processing_failed(
            operation="pdf_to_word",
            error="PDF is encrypted with user password",
            duration_ms=120.0,
            client_id="1234567890.1700000000",
        )

    assert len(dispatched) == 1
    d = dispatched[0]
    assert d["event_name"] == "processing_failed"
    assert d["params"]["tool_name"] == "pdf_to_word"
    assert d["params"]["file_type"] == "pdf"
    assert d["params"]["error_category"] == "invalid_file"
    assert d["params"]["processing_duration_ms"] == 120.0
    assert d["client_id"] == "1234567890.1700000000"


@pytest.mark.anyio
async def test_dispatch_http_handles_network_error(monkeypatch):
    """Network failure or timeout must be safely caught and suppressed."""
    with patch("httpx.AsyncClient.post", side_effect=httpx.ConnectError("Connection refused")):
        # Must not raise
        await _dispatch_http({"client_id": "123.456", "events": []}, "G-TEST12345", "secret")


@pytest.mark.anyio
async def test_dispatch_http_handles_http_4xx(monkeypatch):
    """GA4 4xx rejection must be caught and logged without raising."""
    mock_resp = MagicMock()
    mock_resp.status_code = 400
    with patch("httpx.AsyncClient.post", return_value=mock_resp):
        # Must not raise
        await _dispatch_http({"client_id": "123.456", "events": []}, "G-TEST12345", "secret")


# --- 7. FastAPI Integration with _ga Cookie & event_context_middleware ---

def test_fastapi_request_with_ga_cookie_sets_client_id(client, monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")

    captured_client_id = []

    # Check that client ID was in context during the request
    orig_set = ga4_mp.set_request_client_id

    def spy_set(cid):
        captured_client_id.append(cid)
        return orig_set(cid)

    with patch("scripts.ga4_mp.set_request_client_id", side_effect=spy_set):
        res = client.get(
            "/api/ai-capabilities",
            headers={"Cookie": "_ga=GA1.1.1234567890.1700000000"},
        )
        assert res.status_code == 200

    assert len(captured_client_id) >= 1
    assert "1234567890.1700000000" in captured_client_id

    # Ensure contextvar is reset after request completes
    assert get_request_client_id() is None


def test_fastapi_request_without_ga_cookie_does_not_fail(client, monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")

    res = client.get("/api/ai-capabilities")
    assert res.status_code == 200
    assert get_request_client_id() is None


# --- 8. Event Log timed() and timed_call() Integration ---

@pytest.mark.anyio
async def test_event_log_timed_triggers_ga4_mp_success(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")

    started_events = []
    completed_events = []

    async def dummy_op():
        return "done"

    with patch("scripts.ga4_mp.send_processing_started", side_effect=lambda op, **kw: started_events.append(op)), \
         patch("scripts.ga4_mp.send_processing_completed", side_effect=lambda op, duration_ms=0, **kw: completed_events.append((op, duration_ms))):

        token = set_request_client_id("1234567890.1700000000")
        try:
            res = await event_log.timed("pdf_to_word", dummy_op())
            assert res == "done"
        finally:
            reset_request_client_id(token)

    assert started_events == ["pdf_to_word"]
    assert len(completed_events) == 1
    assert completed_events[0][0] == "pdf_to_word"


@pytest.mark.anyio
async def test_event_log_timed_triggers_ga4_mp_failure(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")

    started_events = []
    failed_events = []

    async def failing_op():
        raise ValueError("Corrupt PDF")

    with patch("scripts.ga4_mp.send_processing_started", side_effect=lambda op, **kw: started_events.append(op)), \
         patch("scripts.ga4_mp.send_processing_failed", side_effect=lambda op, error=None, **kw: failed_events.append((op, error))):

        token = set_request_client_id("1234567890.1700000000")
        try:
            with pytest.raises(ValueError, match="Corrupt PDF"):
                await event_log.timed("pdf_to_word", failing_op())
        finally:
            reset_request_client_id(token)

    assert started_events == ["pdf_to_word"]
    assert len(failed_events) == 1
    assert failed_events[0][0] == "pdf_to_word"
    assert "Corrupt PDF" in str(failed_events[0][1])


def test_event_log_timed_call_triggers_ga4_mp_success(monkeypatch):
    monkeypatch.setenv("GA_MEASUREMENT_ID", "G-TEST12345")
    monkeypatch.setenv("GA_API_SECRET", "test_secret_123")

    started_events = []
    completed_events = []

    with patch("scripts.ga4_mp.send_processing_started", side_effect=lambda op, **kw: started_events.append(op)), \
         patch("scripts.ga4_mp.send_processing_completed", side_effect=lambda op, duration_ms=0, **kw: completed_events.append((op, duration_ms))):

        token = set_request_client_id("1234567890.1700000000")
        try:
            res = event_log.timed_call("merge_pdf", lambda x: x * 2, 21)
            assert res == 42
        finally:
            reset_request_client_id(token)

    assert started_events == ["merge_pdf"]
    assert len(completed_events) == 1
    assert completed_events[0][0] == "merge_pdf"

