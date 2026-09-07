"""Authoritative Backend Google Analytics 4 (GA4) Measurement Protocol Dispatcher.

Sends backend-authoritative execution events (`processing_started`, `processing_completed`,
`processing_failed`) to GA4 via the Measurement Protocol API:
https://www.google-analytics.com/mp/collect?measurement_id=...&api_secret=...

Guarantees:
1. Privacy: Strictly filters all parameters through scripts.ga4_schema. Never sends
   filenames, file contents, OCR text, emails, user IDs, paths, or raw stack traces.
2. Resilience: Completely off the critical request path. Async / background dispatch,
   short 2.0s timeout, all exceptions caught and logged with structured logging. Analytics
   failures NEVER affect file conversion responses.
3. Correlation & Identity: Extracts GA client ID from first-party _ga cookie or
   X-GA-Client-ID request header. If no valid GA identifier exists, correlation is not
   possible and dispatch is safely skipped. Never invents synthetic identifiers or substitutes PII.
4. Security: Gated by environment variables. GA_API_SECRET is backend-only and never
   exposed in client responses or log messages.
"""
from __future__ import annotations

import asyncio
import contextvars
import logging
import os
import re
import threading
from typing import Any, Dict, Optional

import httpx

from scripts.ga4_schema import (
    CanonicalEvent,
    classify_error_category,
    sanitize_event_params,
    sanitize_file_type,
    sanitize_tool_name,
)

logger = logging.getLogger("file_forge.ga4_mp")

GA4_MP_ENDPOINT = "https://www.google-analytics.com/mp/collect"
DEFAULT_TIMEOUT_SECONDS = 2.0

_GA_TAG_RE = re.compile(r"^(?:G|GT)-[A-Za-z0-9_-]{4,64}$")
_GA_COOKIE_CID_RE = re.compile(r"^(?:GA[0-9]+\.[0-9]+\.)?([0-9]+\.[0-9]+)$")
_GA_RAW_CID_RE = re.compile(r"^[a-zA-Z0-9_.-]{1,64}$")

_request_client_id: contextvars.ContextVar[Optional[str]] = contextvars.ContextVar(
    "ff_ga_client_id", default=None
)


def get_measurement_id() -> str:
    """Return the configured GA4 Measurement ID (non-secret)."""
    return (
        os.environ.get("GA_MEASUREMENT_ID", "").strip()
        or os.environ.get("GOOGLE_ANALYTICS_ID", "").strip()
    )


def get_api_secret() -> str:
    """Return the configured GA4 Measurement Protocol API Secret (backend-only)."""
    return os.environ.get("GA_API_SECRET", "").strip()


def is_ga4_mp_enabled() -> bool:
    """Check if backend GA4 Measurement Protocol tracking is fully configured and enabled."""
    m_id = get_measurement_id()
    api_secret = get_api_secret()
    if not m_id or not api_secret:
        return False
    if not _GA_TAG_RE.fullmatch(m_id):
        return False
    return True


is_enabled = is_ga4_mp_enabled
classify_error = classify_error_category


def validate_client_id(client_id_str: Optional[str]) -> Optional[str]:
    """Validate client_id string ensuring it adheres to GA client_id format without PII."""
    return extract_client_id_from_cookie(client_id_str)


def extract_client_id_from_cookie(cookie_val: Optional[str]) -> Optional[str]:
    """Parse and validate client_id from a raw _ga cookie string."""
    if not cookie_val:
        return None
    val = str(cookie_val).strip()
    match = _GA_COOKIE_CID_RE.fullmatch(val)
    if match:
        return match.group(1)
    if _GA_RAW_CID_RE.fullmatch(val) and ("@" not in val and "/" not in val and "\\" not in val):
        return val
    return None


def extract_client_id_from_header(header_val: Optional[str]) -> Optional[str]:
    """Validate client_id from an explicit X-GA-Client-ID header."""
    if not header_val:
        return None
    val = str(header_val).strip()
    if _GA_RAW_CID_RE.fullmatch(val) and ("@" not in val and "/" not in val and "\\" not in val):
        return val
    return None


def extract_client_id(request: Any) -> Optional[str]:
    """Extract and validate GA client_id from a FastAPI / Starlette Request."""
    if request is None:
        return None

    cookies = getattr(request, "cookies", None)
    if cookies and isinstance(cookies, dict):
        ga_cookie = cookies.get("_ga")
        cid = extract_client_id_from_cookie(ga_cookie)
        if cid:
            return cid

    headers = getattr(request, "headers", None)
    if headers:
        header_cid = headers.get("x-ga-client-id") or headers.get("x-client-id")
        cid = extract_client_id_from_header(header_cid)
        if cid:
            return cid

    return None


def set_request_client_id(client_id: Optional[str]) -> contextvars.Token:
    """Set the GA client_id ContextVar for the current request."""
    return _request_client_id.set(client_id)


def reset_request_client_id(token: contextvars.Token) -> None:
    """Reset the GA client_id ContextVar."""
    _request_client_id.reset(token)


def get_request_client_id() -> Optional[str]:
    """Get the current request's GA client_id ContextVar."""
    return _request_client_id.get()


def infer_file_type_from_operation(operation: str) -> Optional[str]:
    """Infer coarse file type from operation name if not explicitly passed."""
    if not operation:
        return None
    op = operation.lower()
    if op.startswith("pdf") or "_pdf" in op:
        return "pdf"
    if op.startswith("heic"):
        return "heic"
    if op.startswith("word") or "docx" in op:
        return "docx"
    if op.startswith("excel") or "xlsx" in op:
        return "xlsx"
    if op.startswith("csv"):
        return "csv"
    if op.startswith("ppt"):
        return "pptx"
    if op.startswith("epub"):
        return "epub"
    if any(k in op for k in ("resize", "crop", "compress_image", "rotate_image", "watermark_image")):
        return "image"
    return None


def build_mp_payload(
    event_name: str,
    params: Dict[str, Any],
    client_id: str,
) -> Dict[str, Any]:
    """Construct a clean, schema-sanitized GA4 Measurement Protocol request body."""
    sanitized_params = sanitize_event_params(event_name, params)
    return {
        "client_id": client_id,
        "events": [
            {
                "name": event_name,
                "params": sanitized_params,
            }
        ],
    }


async def _dispatch_http(payload: Dict[str, Any], measurement_id: str, api_secret: str) -> None:
    """Perform async HTTP POST to GA4 Measurement Protocol endpoint."""
    url = f"{GA4_MP_ENDPOINT}?measurement_id={measurement_id}&api_secret={api_secret}"
    timeout = httpx.Timeout(DEFAULT_TIMEOUT_SECONDS, connect=DEFAULT_TIMEOUT_SECONDS)
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            if resp.status_code >= 400:
                logger.warning(
                    "GA4 Measurement Protocol rejected payload: HTTP %d",
                    resp.status_code,
                )
    except Exception as exc:
        logger.warning("GA4 Measurement Protocol delivery failed: %s", type(exc).__name__)


def send_ga4_mp_event(
    event_name: str,
    params: Dict[str, Any],
    client_id: Optional[str] = None,
) -> None:
    """Dispatch a backend GA4 event non-blockingly."""
    if not is_ga4_mp_enabled():
        return

    m_id = get_measurement_id()
    secret = get_api_secret()

    cid = client_id or get_request_client_id()
    if not cid:
        logger.debug(
            "Skipping GA4 MP dispatch for '%s': no client_id available for session correlation",
            event_name,
        )
        return

    try:
        payload = build_mp_payload(event_name, params, cid)
    except Exception as exc:
        logger.warning("Failed to build GA4 MP payload: %s", exc)
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_dispatch_http(payload, m_id, secret))
    except RuntimeError:
        def _run_in_thread():
            try:
                asyncio.run(_dispatch_http(payload, m_id, secret))
            except Exception:
                pass

        t = threading.Thread(target=_run_in_thread, daemon=True)
        t.start()


def send_processing_started(
    operation: str,
    file_type: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """Dispatch backend processing_started event."""
    tool_name = sanitize_tool_name(operation)
    ft = sanitize_file_type(file_type) or infer_file_type_from_operation(operation)
    params: Dict[str, Any] = {}
    if tool_name:
        params["tool_name"] = tool_name
    if ft:
        params["file_type"] = ft
    send_ga4_mp_event(CanonicalEvent.PROCESSING_STARTED.value, params, client_id=client_id)


def send_processing_completed(
    operation: str,
    duration_ms: float,
    file_type: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """Dispatch backend authoritative processing_completed event (Key Event / Conversion)."""
    tool_name = sanitize_tool_name(operation)
    ft = sanitize_file_type(file_type) or infer_file_type_from_operation(operation)
    params: Dict[str, Any] = {
        "processing_duration_ms": duration_ms,
    }
    if tool_name:
        params["tool_name"] = tool_name
    if ft:
        params["file_type"] = ft
    send_ga4_mp_event(CanonicalEvent.PROCESSING_COMPLETED.value, params, client_id=client_id)


def send_processing_failed(
    operation: str,
    error: Any,
    duration_ms: Optional[float] = None,
    file_type: Optional[str] = None,
    client_id: Optional[str] = None,
) -> None:
    """Dispatch backend authoritative processing_failed event with coarse error classification."""
    tool_name = sanitize_tool_name(operation)
    ft = sanitize_file_type(file_type) or infer_file_type_from_operation(operation)
    err_cat = classify_error_category(error)
    params: Dict[str, Any] = {
        "error_category": err_cat,
    }
    if tool_name:
        params["tool_name"] = tool_name
    if ft:
        params["file_type"] = ft
    if duration_ms is not None:
        params["processing_duration_ms"] = duration_ms
    send_ga4_mp_event(CanonicalEvent.PROCESSING_FAILED.value, params, client_id=client_id)
