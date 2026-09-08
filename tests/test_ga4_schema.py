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
    # Pure frontend events
    assert EVENT_DEFINITIONS[CanonicalEvent.PAGE_VIEW].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.TOOL_OPEN].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.FILE_SELECTED].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_CANCELLED].owner == EventOwner.FRONTEND
    assert EVENT_DEFINITIONS[CanonicalEvent.FILE_DOWNLOADED].owner == EventOwner.FRONTEND
    # DUAL: backend MP for server-side; frontend gtag for local on-device processing
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_COMPLETED].owner == EventOwner.DUAL
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_FAILED].owner == EventOwner.DUAL
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


# ---------------------------------------------------------------------------
# Audit fix: processing_duration_ms must survive sanitization in processing_failed
# ---------------------------------------------------------------------------

def test_processing_failed_allows_duration_ms():
    """BUG FIX: processing_duration_ms must not be stripped from processing_failed.

    Before this fix, send_processing_failed() added processing_duration_ms to params
    but PROCESSING_FAILED allowed only ['tool_name', 'file_type', 'error_category'].
    sanitize_event_params() correctly stripped any key not in allowed_parameters, so
    the duration was silently discarded. This test verifies the schema was fixed.
    """
    raw_params = {
        'tool_name': 'pdf-to-word',
        'file_type': 'pdf',
        'error_category': 'timeout',
        'processing_duration_ms': 45000,
    }
    sanitized = sanitize_event_params('processing_failed', raw_params)
    assert 'processing_duration_ms' in sanitized, (
        'processing_duration_ms must survive sanitization in processing_failed events '
        "to enable 'which tools fail after long processing?' analysis"
    )
    assert sanitized['processing_duration_ms'] == 45000


def test_processing_failed_duration_ms_is_integer():
    """Duration stored as integer (rounded ms), not float."""
    raw_params = {
        'tool_name': 'compress-pdf',
        'file_type': 'pdf',
        'error_category': 'server_error',
        'processing_duration_ms': '12345.7',
    }
    sanitized = sanitize_event_params('processing_failed', raw_params)
    assert isinstance(sanitized['processing_duration_ms'], int)
    assert sanitized['processing_duration_ms'] == 12346


def test_processing_failed_strips_pii_even_with_duration():
    """PII must still be stripped from processing_failed even with duration present."""
    raw_params = {
        'tool_name': 'ocr-pdf',
        'file_type': 'pdf',
        'error_category': 'ocr',
        'processing_duration_ms': 8000,
        'filename': 'my_document.pdf',
        'user_id': 'usr_12345',
        'stack_trace': 'Traceback...',
    }
    sanitized = sanitize_event_params('processing_failed', raw_params)
    assert sanitized.get('processing_duration_ms') == 8000
    assert 'filename' not in sanitized
    assert 'user_id' not in sanitized
    assert 'stack_trace' not in sanitized


def test_processing_completed_allows_duration_ms():
    """processing_completed already allowed duration -- regression guard."""
    raw_params = {
        'tool_name': 'compress-pdf',
        'file_type': 'pdf',
        'processing_duration_ms': 3200,
    }
    sanitized = sanitize_event_params('processing_completed', raw_params)
    assert sanitized['processing_duration_ms'] == 3200


def test_processing_failed_is_not_key_event():
    """Only processing_completed is a key event; processing_failed is not."""
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_COMPLETED].candidate_key_event is True
    assert EVENT_DEFINITIONS[CanonicalEvent.PROCESSING_FAILED].candidate_key_event is False


def test_required_custom_definitions_marked_in_schema():
    """All custom-dimension/metric params are flagged requires_custom_definition=True."""
    for param_name in ('tool_name', 'file_type', 'error_category', 'processing_duration_ms'):
        assert PARAMETER_DEFINITIONS[param_name].requires_custom_definition is True


def test_page_path_and_title_are_built_in_not_custom():
    """page_path and page_title are built-in GA4 dimensions -- no custom definition needed."""
    assert PARAMETER_DEFINITIONS['page_path'].requires_custom_definition is False
    assert PARAMETER_DEFINITIONS['page_title'].requires_custom_definition is False
