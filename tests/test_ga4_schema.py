"""Tests for the canonical GA4 schema module (public/scripts/ga4_schema.py)."""
import json
import pytest

from scripts.ga4_schema import (
    CanonicalEvent,
    ErrorCategory,
    EventOwner,
    ParameterType,
    EVENT_DEFINITIONS,
    FORBIDDEN_PARAMETER_KEYS,
    PARAMETER_DEFINITIONS,
    classify_error_category,
    export_schema_json,
    get_canonical_schema_manifest,
    sanitize_event_params,
    sanitize_file_type,
    sanitize_tool_name,
)


def test_canonical_events_and_parameters_defined():
    expected_events = {
        "page_view",
        "tool_open",
        "file_selected",
        "processing_started",
        "processing_completed",
        "processing_failed",
        "processing_cancelled",
        "file_downloaded",
    }
    actual_events = {e.value for e in CanonicalEvent}
    assert expected_events == actual_events

    expected_params = {
        "tool_name",
        "file_type",
        "error_category",
        "processing_duration_ms",
        "page_path",
        "page_title",
    }
    assert expected_params == set(PARAMETER_DEFINITIONS.keys())


def test_dimensions_and_metrics_classification():
    assert PARAMETER_DEFINITIONS["tool_name"].param_type == ParameterType.DIMENSION
    assert PARAMETER_DEFINITIONS["file_type"].param_type == ParameterType.DIMENSION
    assert PARAMETER_DEFINITIONS["error_category"].param_type == ParameterType.DIMENSION
    assert PARAMETER_DEFINITIONS["processing_duration_ms"].param_type == ParameterType.METRIC


def test_candidate_key_events():
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_COMPLETED].candidate_key_event is True
    assert EVENT_DEFINITIONS[CanonicalEvent.FILE_DOWNLOADED].candidate_key_event is True
    assert EVENT_DEFINITIONS[CanonicalEvent.PAGE_VIEW].candidate_key_event is False
    assert EVENT_DEFINITIONS[CanonicalEvent.TOOL_OPEN].candidate_key_event is False


def test_source_ownership():
    assert EVENT_DEFINITIONS[CanonicalEvent.PAGE_VIEW].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.TOOL_OPEN].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.FILE_SELECTED].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_CANCELLED].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.FILE_DOWNLOADED].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_COMPLETED].owner == EventOwner.BACKEND
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_FAILED].owner == EventOwner.BACKEND
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_STARTED].owner == EventOwner.DUAL


@pytest.mark.parametrize(
    "error_input, expected_category",
    [
        (408, "timeout"),
        (504, "timeout"),
        ("Request timed out after 30s", "timeout"),
        (413, "unsupported_file"),
        (415, "unsupported_file"),
        ("Unsupported MIME format application/x-unknown", "unsupported_file"),
        (400, "invalid_file"),
        (422, "invalid_file"),
        ("Corrupt or encrypted PDF password required", "invalid_file"),
        ("LibreOffice failed to convert document", "libreoffice"),
        ("RapidOCR engine failure in worker", "ocr"),
        ("PaddleOCR model load error", "ocr"),
        (429, "rate_limited"),
        ("Rate limit exceeded. Please wait.", "rate_limited"),
        ("Operation aborted by user", "cancelled"),
        (499, "cancelled"),
        (500, "server_error"),
        (502, "server_error"),
        (503, "server_error"),
        ("Generic conversion failure", "conversion_error"),
        (None, "conversion_error"),
    ],
)
def test_classify_error_category(error_input, expected_category):
    assert classify_error_category(error_input) == expected_category


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("pdf", "pdf"),
        (".PDF", "pdf"),
        ("document.pdf", "pdf"),
        ("application/pdf", "pdf"),
        ("image/jpeg", "jpg"),
        ("photo.JPEG", "jpg"),
        ("data.csv", "csv"),
        ("sheet.XLSX", "xlsx"),
        ("presentation.pptx", "pptx"),
        ("", None),
        (None, None),
        ("../../etc/passwd", "passwd"),
    ],
)
def test_sanitize_file_type(raw, expected):
    assert sanitize_file_type(raw) == expected


@pytest.mark.parametrize(
    "raw, expected",
    [
        ("pdf-to-word", "pdf_to_word"),
        ("remove-password-btn", "remove_password"),
        ("heic_to_jpeg_card", "heic_to_jpeg"),
        ("MERGE-PDF", "merge_pdf"),
        ("", None),
        (None, None),
    ],
)
def test_sanitize_tool_name(raw, expected):
    assert sanitize_tool_name(raw) == expected


def test_sanitize_event_params_strips_forbidden_pii():
    raw_params = {
        "tool_name": "pdf_to_word",
        "file_type": "pdf",
        "filename": "my_secret_passport.pdf",
        "file_content": "binary-data...",
        "ocr_text": "Sensitive extracted document content",
        "email": "user@example.com",
        "user_id": "usr_12345",
        "supabase_id": "550e8400-e29b-41d4-a716-446655440000",
        "order_id": "ord_98765",
        "stack_trace": "Traceback (most recent call last):\nFile 'foo.py'...",
        "path": "/var/tmp/upload_123.pdf",
        "unknown_extra_param": "should_be_stripped",
    }

    sanitized = sanitize_event_params("file_selected", raw_params)

    # Allowed keys preserved and cleaned
    assert sanitized["tool_name"] == "pdf_to_word"
    assert sanitized["file_type"] == "pdf"

    # All forbidden and extra keys removed
    for forbidden in FORBIDDEN_PARAMETER_KEYS:
        assert forbidden not in sanitized
    assert "unknown_extra_param" not in sanitized


def test_sanitize_event_params_validates_types():
    raw_params = {
        "tool_name": "compress-pdf",
        "file_type": "PDF",
        "processing_duration_ms": "1250.6",
    }
    sanitized = sanitize_event_params("processing_completed", raw_params)
    assert sanitized["tool_name"] == "compress_pdf"
    assert sanitized["file_type"] == "pdf"
    assert sanitized["processing_duration_ms"] == 1251
    assert isinstance(sanitized["processing_duration_ms"], int)


def test_sanitize_event_params_error_coarsening():
    raw_params = {
        "tool_name": "ocr-pdf",
        "file_type": "pdf",
        "error_category": "LibreOffice crash at /tmp/file.docx",
    }
    sanitized = sanitize_event_params("processing_failed", raw_params)
    assert sanitized["error_category"] == "libreoffice"


def test_schema_manifest_export():
    manifest = get_canonical_schema_manifest()
    assert manifest["version"] == "1.0.0"
    assert "events" in manifest
    assert "parameters" in manifest
    assert "privacy" in manifest

    json_str = export_schema_json()
    loaded = json.loads(json_str)
    assert loaded["version"] == "1.0.0"
    assert "processing_completed" in loaded["events"]
