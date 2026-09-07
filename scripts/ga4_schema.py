"""Canonical Google Analytics 4 (GA4) Event Schema & Privacy Contract for Forge Files.

This module is the single source of truth for GA4 event instrumentation across Forge Files.
It defines:
- Canonical event names and parameter specifications
- Dimension vs Metric parameter classifications
- Frontend vs Backend event ownership
- Candidate Key Events (conversions)
- Coarse error category classification
- Privacy filtering and sensitive-data sanitization rules

Used by:
- Browser-side tracking (public/static/script.js)
- Backend Measurement Protocol dispatcher (Agent 2)
- GA4 Admin API & Custom Dimension sync tooling (Agent 3)
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass
from enum import Enum
from typing import Any, Dict, List, Optional, Set


class EventOwner(str, Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    DUAL = "dual"


class ParameterType(str, Enum):
    DIMENSION = "dimension"
    METRIC = "metric"


class CanonicalEvent(str, Enum):
    PAGE_VIEW = "page_view"
    TOOL_OPEN = "tool_open"
    FILE_SELECTED = "file_selected"
    PROCESSING_STARTED = "processing_started"
    PROCESSING_COMPLETED = "processing_completed"
    PROCESSING_FAILED = "processing_failed"
    PROCESSING_CANCELLED = "processing_cancelled"
    FILE_DOWNLOADED = "file_downloaded"


class ErrorCategory(str, Enum):
    TIMEOUT = "timeout"
    UNSUPPORTED_FILE = "unsupported_file"
    INVALID_FILE = "invalid_file"
    LIBREOFFICE = "libreoffice"
    OCR = "ocr"
    CONVERSION_ERROR = "conversion_error"
    RATE_LIMITED = "rate_limited"
    SERVER_ERROR = "server_error"
    CANCELLED = "cancelled"


VALID_ERROR_CATEGORIES: Set[str] = {c.value for c in ErrorCategory}


# Forbidden parameter names and sensitive patterns that MUST NEVER be sent to GA4
FORBIDDEN_PARAMETER_KEYS: Set[str] = {
    "filename",
    "file_name",
    "file",
    "files",
    "file_content",
    "content",
    "contents",
    "text",
    "ocr_text",
    "document_text",
    "email",
    "user_id",
    "userid",
    "supabase_id",
    "request_id",
    "requestid",
    "order_id",
    "orderid",
    "stack_trace",
    "stacktrace",
    "traceback",
    "path",
    "temp_path",
    "filepath",
    "file_path",
    "exception",
    "exception_message",
    "raw_error",
    "ip",
    "ip_address",
    "password",
    "token",
}

# Regex matching path-like or file-like strings (scrubbing safeguard)
_PATH_OR_FILE_RE = re.compile(
    r"(?:[A-Za-z]:[\\/]|/[a-zA-Z0-9_\.\-]+/|\b[a-zA-Z0-9_\.\-]+\.(?:pdf|docx?|xlsx?|pptx?|jpe?g|png|heic|webp|txt|zip)\b)",
    re.IGNORECASE,
)
_EMAIL_RE = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
_UUID_RE = re.compile(r"\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b", re.IGNORECASE)


@dataclass(frozen=True)
class ParameterDefinition:
    name: str
    param_type: ParameterType
    description: str
    data_type: str  # "string" | "integer"
    requires_custom_definition: bool
    ga4_scope: str  # "EVENT"


@dataclass(frozen=True)
class EventDefinition:
    name: CanonicalEvent
    owner: EventOwner
    description: str
    allowed_parameters: List[str]
    candidate_key_event: bool


# Canonical parameter registry
PARAMETER_DEFINITIONS: Dict[str, ParameterDefinition] = {
    "tool_name": ParameterDefinition(
        name="tool_name",
        param_type=ParameterType.DIMENSION,
        description="Normalized tool or operation identifier (e.g., pdf_to_word, compress_pdf, heic_to_jpeg).",
        data_type="string",
        requires_custom_definition=True,
        ga4_scope="EVENT",
    ),
    "file_type": ParameterDefinition(
        name="file_type",
        param_type=ParameterType.DIMENSION,
        description="Normalized file extension/format without leading dot (e.g., pdf, docx, png). Never filenames.",
        data_type="string",
        requires_custom_definition=True,
        ga4_scope="EVENT",
    ),
    "error_category": ParameterDefinition(
        name="error_category",
        param_type=ParameterType.DIMENSION,
        description="Standardized coarse error classification (timeout, unsupported_file, invalid_file, etc.).",
        data_type="string",
        requires_custom_definition=True,
        ga4_scope="EVENT",
    ),
    "processing_duration_ms": ParameterDefinition(
        name="processing_duration_ms",
        param_type=ParameterType.METRIC,
        description="Execution time of the conversion or operation in milliseconds.",
        data_type="integer",
        requires_custom_definition=True,
        ga4_scope="EVENT",
    ),
    "page_path": ParameterDefinition(
        name="page_path",
        param_type=ParameterType.DIMENSION,
        description="Standard GA4 page path (e.g., /app/pdf, /about).",
        data_type="string",
        requires_custom_definition=False,
        ga4_scope="EVENT",
    ),
    "page_title": ParameterDefinition(
        name="page_title",
        param_type=ParameterType.DIMENSION,
        description="Standard GA4 page title.",
        data_type="string",
        requires_custom_definition=False,
        ga4_scope="EVENT",
    ),
}

# Canonical event registry
EVENT_DEFINITIONS: Dict[CanonicalEvent, EventDefinition] = {
    CanonicalEvent.PAGE_VIEW: EventDefinition(
        name=CanonicalEvent.PAGE_VIEW,
        owner=EventOwner.FRONTEND,
        description="Visitor viewed a page or triggered an in-app virtual SPA drilldown.",
        allowed_parameters=["page_path", "page_title"],
        candidate_key_event=False,
    ),
    CanonicalEvent.TOOL_OPEN: EventDefinition(
        name=CanonicalEvent.TOOL_OPEN,
        owner=EventOwner.FRONTEND,
        description="Visitor opened a tool category or selected a specific tool action card.",
        allowed_parameters=["tool_name"],
        candidate_key_event=False,
    ),
    CanonicalEvent.FILE_SELECTED: EventDefinition(
        name=CanonicalEvent.FILE_SELECTED,
        owner=EventOwner.FRONTEND,
        description="Visitor selected, dropped, or queued one or more files for conversion.",
        allowed_parameters=["tool_name", "file_type"],
        candidate_key_event=False,
    ),
    CanonicalEvent.PROCESSING_STARTED: EventDefinition(
        name=CanonicalEvent.PROCESSING_STARTED,
        owner=EventOwner.DUAL,
        description="File processing pipeline initiated on client or server.",
        allowed_parameters=["tool_name", "file_type"],
        candidate_key_event=False,
    ),
    CanonicalEvent.PROCESSING_COMPLETED: EventDefinition(
        name=CanonicalEvent.PROCESSING_COMPLETED,
        owner=EventOwner.BACKEND,
        description="File processing completed successfully. Primary authoritative conversion success event.",
        allowed_parameters=["tool_name", "file_type", "processing_duration_ms"],
        candidate_key_event=True,
    ),
    CanonicalEvent.PROCESSING_FAILED: EventDefinition(
        name=CanonicalEvent.PROCESSING_FAILED,
        owner=EventOwner.BACKEND,
        description="File processing failed with an error, categorized coarsely.",
        allowed_parameters=["tool_name", "file_type", "error_category"],
        candidate_key_event=False,
    ),
    CanonicalEvent.PROCESSING_CANCELLED: EventDefinition(
        name=CanonicalEvent.PROCESSING_CANCELLED,
        owner=EventOwner.FRONTEND,
        description="Visitor explicitly cancelled an inflight processing operation.",
        allowed_parameters=["tool_name"],
        candidate_key_event=False,
    ),
    CanonicalEvent.FILE_DOWNLOADED: EventDefinition(
        name=CanonicalEvent.FILE_DOWNLOADED,
        owner=EventOwner.FRONTEND,
        description="Visitor clicked or triggered download of the converted/processed file.",
        allowed_parameters=["tool_name", "file_type"],
        candidate_key_event=True,
    ),
}


# --- Helpers & Sanitization ---


def classify_error_category(exc_or_msg: Any) -> str:
    """Map an exception, HTTP status code, or error message to a coarse error category.

    Strictly guarantees that no raw exception message or path is returned.
    """
    if exc_or_msg is None:
        return ErrorCategory.CONVERSION_ERROR.value

    if isinstance(exc_or_msg, int):
        if exc_or_msg in (408, 504):
            return ErrorCategory.TIMEOUT.value
        if exc_or_msg in (413, 415):
            return ErrorCategory.UNSUPPORTED_FILE.value
        if exc_or_msg in (400, 422):
            return ErrorCategory.INVALID_FILE.value
        if exc_or_msg == 429:
            return ErrorCategory.RATE_LIMITED.value
        if exc_or_msg == 499:
            return ErrorCategory.CANCELLED.value
        if exc_or_msg >= 500:
            return ErrorCategory.SERVER_ERROR.value
        return ErrorCategory.CONVERSION_ERROR.value

    s = str(exc_or_msg).lower()

    if "abort" in s or "cancel" in s:
        return ErrorCategory.CANCELLED.value
    if "rate" in s and ("limit" in s or "429" in s):
        return ErrorCategory.RATE_LIMITED.value
    if "timeout" in s or "timed out" in s:
        return ErrorCategory.TIMEOUT.value
    if "libreoffice" in s or "soffice" in s:
        return ErrorCategory.LIBREOFFICE.value
    if "ocr" in s or "paddle" in s or "rapidocr" in s:
        return ErrorCategory.OCR.value
    if "unsupported" in s or "not supported" in s or "format" in s or "mime" in s:
        return ErrorCategory.UNSUPPORTED_FILE.value
    if "invalid" in s or "corrupt" in s or "password" in s or "encrypted" in s or "bad file" in s:
        return ErrorCategory.INVALID_FILE.value
    if "500" in s or "502" in s or "503" in s or "server error" in s:
        return ErrorCategory.SERVER_ERROR.value

    return ErrorCategory.CONVERSION_ERROR.value


def sanitize_file_type(raw_type: Optional[str]) -> Optional[str]:
    """Extract and normalize clean file extension/type (e.g. 'pdf', 'png', 'docx').

    Guarantees no filename, path, or query string is leaked.
    """
    if not raw_type:
        return None
    s = str(raw_type).strip().lower()

    # If MIME type (e.g. 'application/pdf', 'image/jpeg')
    if "/" in s:
        s = s.split("/")[-1].split("+")[0].split(";")[0].strip()

    # If filename passed by mistake, extract extension only
    if "." in s:
        s = s.rsplit(".", 1)[-1]

    # Strip any trailing query or non-alphanumeric chars
    s = re.sub(r"[^a-z0-9]", "", s)
    if not s or len(s) > 10:
        return None

    # Normalization aliases
    aliases = {
        "jpeg": "jpg",
        "tiff": "tif",
        "vndopenxmlformatsofficedocumentwordprocessingml": "docx",
        "vndopenxmlformatsofficedocumentspreadsheetml": "xlsx",
        "vndopenxmlformatsofficedocumentpresentationml": "pptx",
    }
    return aliases.get(s, s)


def sanitize_tool_name(raw_tool: Optional[str]) -> Optional[str]:
    """Normalize tool identifier to snake_case alphanumeric string (<= 50 chars)."""
    if not raw_tool:
        return None
    s = str(raw_tool).strip().lower()
    # Strip common UI suffixes like '-btn', '_button', etc.
    s = re.sub(r"[-_](?:btn|button|card|action)$", "", s)
    # Convert hyphens to underscores
    s = s.replace("-", "_").replace(" ", "_").replace("/", "_")
    # Clean leading/trailing underscores and strip non-alphanumeric
    s = re.sub(r"[^a-z0-9_]", "", s).strip("_")
    if not s:
        return None
    return s[:50]


def sanitize_event_params(event_name: str, params: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Sanitize and validate event parameters strictly according to privacy and schema rules.

    - Strips all forbidden parameter keys (filenames, text, emails, user IDs, paths, etc.).
    - Drops any parameter not defined for the event.
    - Sanitizes parameter values (coarsens error categories, strips file paths, bounds numbers).
    - Returns a clean dictionary ready for GA4 transmission.
    """
    if not params or not isinstance(params, dict):
        return {}

    sanitized: Dict[str, Any] = {}

    # Look up event definition if canonical
    event_enum: Optional[CanonicalEvent] = None
    for ce in CanonicalEvent:
        if ce.value == event_name:
            event_enum = ce
            break

    allowed_keys: Optional[List[str]] = (
        EVENT_DEFINITIONS[event_enum].allowed_parameters if event_enum else None
    )

    for key, val in params.items():
        if val is None:
            continue
        key_str = str(key).lower().strip()

        # Reject forbidden keys immediately
        if key_str in FORBIDDEN_PARAMETER_KEYS:
            continue

        # If canonical event, reject keys not in allowed list
        if allowed_keys is not None and key_str not in allowed_keys:
            continue

        # Specific parameter rules
        if key_str == "tool_name":
            clean_tool = sanitize_tool_name(val)
            if clean_tool:
                sanitized["tool_name"] = clean_tool

        elif key_str == "file_type":
            clean_ft = sanitize_file_type(val)
            if clean_ft:
                sanitized["file_type"] = clean_ft

        elif key_str == "error_category":
            if str(val).lower() in VALID_ERROR_CATEGORIES:
                sanitized["error_category"] = str(val).lower()
            else:
                sanitized["error_category"] = classify_error_category(val)

        elif key_str == "processing_duration_ms":
            try:
                ms = int(round(float(val)))
                if 0 <= ms <= 86400000:  # Max 24 hours
                    sanitized["processing_duration_ms"] = ms
            except (ValueError, TypeError):
                continue

        elif key_str in ("page_path", "page_title"):
            val_str = str(val).strip()
            # Ensure no PII in page path or title
            if _PATH_OR_FILE_RE.search(val_str) or _EMAIL_RE.search(val_str) or _UUID_RE.search(val_str):
                val_str = _EMAIL_RE.sub("[email]", val_str)
                val_str = _UUID_RE.sub("[id]", val_str)
            sanitized[key_str] = val_str[:120]

        else:
            # Safe generic fallback (only if not restricted by canonical schema)
            if allowed_keys is None:
                val_str = str(val).strip()
                if not (_PATH_OR_FILE_RE.search(val_str) or _EMAIL_RE.search(val_str) or _UUID_RE.search(val_str)):
                    sanitized[key_str[:40]] = val_str[:100]

    return sanitized


def get_canonical_schema_manifest() -> Dict[str, Any]:
    """Return machine-readable manifest of the entire canonical schema."""
    return {
        "version": "1.0.0",
        "description": "Forge Files Canonical GA4 Analytics Schema Contract",
        "parameters": {
            p_name: {
                "name": p.name,
                "type": p.param_type.value,
                "data_type": p.data_type,
                "description": p.description,
                "requires_custom_definition": p.requires_custom_definition,
                "ga4_scope": p.ga4_scope,
            }
            for p_name, p in PARAMETER_DEFINITIONS.items()
        },
        "events": {
            e_name.value: {
                "name": e.name.value,
                "owner": e.owner.value,
                "description": e.description,
                "allowed_parameters": e.allowed_parameters,
                "candidate_key_event": e.candidate_key_event,
            }
            for e_name, e in EVENT_DEFINITIONS.items()
        },
        "error_categories": sorted(list(VALID_ERROR_CATEGORIES)),
        "privacy": {
            "forbidden_parameters": sorted(list(FORBIDDEN_PARAMETER_KEYS)),
            "rules": [
                "Never send filenames or raw file paths.",
                "Never send file contents or extracted OCR text.",
                "Never send user IDs, emails, order IDs, or raw request IDs.",
                "Never send unparsed exception messages or stack traces.",
                "Always map failures to coarse error categories.",
            ],
        },
    }


def export_schema_json(indent: int = 2) -> str:
    """Export the canonical schema manifest as formatted JSON."""
    return json.dumps(get_canonical_schema_manifest(), indent=indent)
