# Forge Files — GA4 Canonical Analytics Schema & Integration Contract

> **Version**: 1.0.0  
> **Status**: APPROVED CONTRACT (Phase 1 & Phase 2)  
> **Target Audience**: All agents working on Forge Files analytics (Agent 1 Frontend, Agent 2 Backend Measurement Protocol, Agent 3 GA4 Admin API Sync & Property Provisioning).

---

## 1. Executive Summary

This document establishes the canonical event schema, parameter definitions, source ownership, privacy rules, and integration contract for Google Analytics 4 across Forge Files.

- **Frontend (Agent 1)** owns client-side behavioral events: `page_view`, `tool_open`, `file_selected`, `processing_cancelled`, and `file_downloaded`.
- **Backend Measurement Protocol (Agent 2)** owns authoritative operation execution events: `processing_completed`, `processing_failed`, and optionally `processing_started`.
- **GA4 Admin API & Provisioning (Agent 3)** configures the target GA4 Property, registers Custom Dimensions and Custom Metrics, and marks Candidate Key Events as conversion events based on this exact schema.

---

## 2. Event & Parameter Integration Matrix

| Event | Owner | Parameters | Custom Definition Required? | Candidate Key Event? | Description |
|---|---|---|---|---|---|
| `page_view` | **Frontend** | `page_path` *(std)*, `page_title` *(std)* | No (Standard GA4) | No | Initial page load and virtual in-app SPA tool drill-down transitions. |
| `tool_open` | **Frontend** | `tool_name` | Yes (`tool_name` Dimension) | No | Visitor navigated to a tool category or clicked a specific action card. |
| `file_selected` | **Frontend** | `tool_name`, `file_type` | Yes (`tool_name`, `file_type` Dimensions) | No | Visitor uploaded, dropped, or selected file(s) for conversion. |
| `processing_started` | **Dual** | `tool_name`, `file_type` | Yes (`tool_name`, `file_type` Dimensions) | No | Pipeline execution initiated. |
| `processing_completed` | **Dual** | `tool_name`, `file_type`, `processing_duration_ms` | Yes (`tool_name`, `file_type` Dims; `processing_duration_ms` Metric) | **YES** | Authoritative conversion success event. Emitted via Backend MP for server processing; emitted via browser gtag ONLY for local on-device tools. |
| `processing_failed` | **Dual** | `tool_name`, `file_type`, `error_category`, `processing_duration_ms` | Yes (`tool_name`, `file_type`, `error_category` Dims; `processing_duration_ms` Metric) | No | Operation failure event with coarse error categorization and wall-clock execution duration. |
| `processing_cancelled` | **Frontend** | `tool_name` | Yes (`tool_name` Dimension) | No | Visitor clicked Cancel while an operation was in flight. |
| `file_downloaded` | **Frontend** | `tool_name`, `file_type` | Yes (`tool_name`, `file_type` Dimensions) | **YES** | Visitor clicked download or triggered native save of converted output. |
| `purchase` | **Backend (Webhook)** | `item_id`, `value` *(opt)*, `currency` *(opt)*, `payment_provider` *(opt)* | No (Standard GA4 Ecommerce) | **YES** (Standard) | Authoritative purchase event dispatched strictly from verified webhook handlers upon entitlement grant. No PII or payment IDs sent. |

---

## 3. Parameter Specifications

| Parameter Name | Type | Data Type | Scope | GA4 Custom Definition | Description & Examples |
|---|---|---|---|---|---|
| `tool_name` | **Dimension** | string | EVENT | Custom Dimension (`tool_name`) | Snake_case tool identifier, e.g. `pdf_to_word`, `compress_pdf`, `merge_pdf`, `heic_to_jpeg`. Max 50 chars. |
| `file_type` | **Dimension** | string | EVENT | Custom Dimension (`file_type`) | Lowercase file format extension, e.g. `pdf`, `docx`, `png`, `jpg`, `xlsx`. Max 10 chars. **Never a filename**. |
| `error_category` | **Dimension** | string | EVENT | Custom Dimension (`error_category`) | Coarse error category string (one of the 9 allowed categories). Max 30 chars. **Never raw error messages**. |
| `processing_duration_ms` | **Metric** | integer | EVENT | Custom Metric (`processing_duration_ms`, Unit: Milliseconds) | Wall-clock execution time in milliseconds (0 to 86,400,000). |
| `page_path` | **Dimension** | string | EVENT | Standard GA4 | Virtual or real page path (e.g. `/`, `/app/pdf`, `/pdf-to-word`). |
| `page_title` | **Dimension** | string | EVENT | Standard GA4 | Document title. |

---

## 4. Privacy & Sanitization Mandate (FAIL-CLOSED)

To comply with global privacy standards, Google Analytics Terms of Service, and Forge Files data governance, the following data **MUST NEVER** be transmitted:

1. **No Filenames**: Never transmit `filename`, `file_name`, or original file identifiers (e.g. `resume.pdf` must be stripped to `file_type="pdf"`).
2. **No Document Content**: Never transmit document body, OCR text, form values, or password strings.
3. **No User Identifiers**: Never transmit emails, usernames, Supabase user IDs, or IP addresses to GA4.
4. **No Financial / Transaction PII**: Never transmit order IDs, checkout session tokens, payment IDs (`transaction_id`), or payment card references.
5. **No System Paths or Traces**: Never transmit temporary paths, filesystem paths (`/tmp/...`), stack traces, or raw exception strings.
6. **Coarse Errors Only**: All failures must be mapped to one of the **9 standard error categories**:
   - `timeout`
   - `unsupported_file`
   - `invalid_file`
   - `libreoffice`
   - `ocr`
   - `conversion_error`
   - `rate_limited`
   - `server_error`
   - `cancelled`

The Python module `public/scripts/ga4_schema.py` provides `classify_error_category()` and `sanitize_event_params()` for automated compliance.

---

## 5. Machine-Readable Schema (Importable Python & JSON)

### Python Usage (Backend & Sync Tooling)
```python
from scripts.ga4_schema import (
    CanonicalEvent,
    ErrorCategory,
    classify_error_category,
    sanitize_event_params,
    get_canonical_schema_manifest,
)

# Sanitize backend Measurement Protocol payload
payload = sanitize_event_params(
    CanonicalEvent.PROCESSING_COMPLETED.value,
    {
        "tool_name": "pdf_to_word",
        "file_type": "pdf",
        "processing_duration_ms": 1420,
        "filename": "confidential_document.pdf",  # Automatically stripped!
    },
)
# Result: {"tool_name": "pdf_to_word", "file_type": "pdf", "processing_duration_ms": 1420}
```

### JSON Schema Manifest
```json
{
  "version": "1.1.0",
  "description": "Forge Files Canonical GA4 Analytics Schema Contract",
  "parameters": {
    "tool_name": {
      "name": "tool_name",
      "type": "dimension",
      "data_type": "string",
      "description": "Normalized tool or operation identifier (e.g., pdf_to_word, compress_pdf, heic_to_jpeg).",
      "requires_custom_definition": true,
      "ga4_scope": "EVENT"
    },
    "file_type": {
      "name": "file_type",
      "type": "dimension",
      "data_type": "string",
      "description": "Normalized file extension/format without leading dot (e.g., pdf, docx, png). Never filenames.",
      "requires_custom_definition": true,
      "ga4_scope": "EVENT"
    },
    "error_category": {
      "name": "error_category",
      "type": "dimension",
      "data_type": "string",
      "description": "Standardized coarse error classification (timeout, unsupported_file, invalid_file, etc.).",
      "requires_custom_definition": true,
      "ga4_scope": "EVENT"
    },
    "processing_duration_ms": {
      "name": "processing_duration_ms",
      "type": "metric",
      "data_type": "integer",
      "description": "Execution time of the conversion or operation in milliseconds.",
      "requires_custom_definition": true,
      "ga4_scope": "EVENT"
    }
  },
  "events": {
    "page_view": {
      "name": "page_view",
      "owner": "frontend",
      "allowed_parameters": ["page_path", "page_title"],
      "candidate_key_event": false
    },
    "tool_open": {
      "name": "tool_open",
      "owner": "frontend",
      "allowed_parameters": ["tool_name"],
      "candidate_key_event": false
    },
    "file_selected": {
      "name": "file_selected",
      "owner": "frontend",
      "allowed_parameters": ["tool_name", "file_type"],
      "candidate_key_event": false
    },
    "processing_started": {
      "name": "processing_started",
      "owner": "dual",
      "allowed_parameters": ["tool_name", "file_type"],
      "candidate_key_event": false
    },
    "processing_completed": {
      "name": "processing_completed",
      "owner": "dual",
      "allowed_parameters": ["tool_name", "file_type", "processing_duration_ms"],
      "candidate_key_event": true
    },
    "processing_failed": {
      "name": "processing_failed",
      "owner": "dual",
      "allowed_parameters": ["tool_name", "file_type", "error_category", "processing_duration_ms"],
      "candidate_key_event": false
    },
    "processing_cancelled": {
      "name": "processing_cancelled",
      "owner": "frontend",
      "allowed_parameters": ["tool_name"],
      "candidate_key_event": false
    },
    "file_downloaded": {
      "name": "file_downloaded",
      "owner": "frontend",
      "allowed_parameters": ["tool_name", "file_type"],
      "candidate_key_event": true
    }
  }
}
```

---

## 6. Dual-Emitter Contract (`processing_completed` & `file_processed`)

Forge Files maintains two complementary tracking systems with distinct responsibilities:

1. **GA4 Canonical Events**:
   - `processing_completed` is the canonical conversion event in GA4.
   - **Server-side processing**: The backend Measurement Protocol (`public/scripts/ga4_mp.py`) dispatches `processing_completed`. The browser does NOT dispatch this event, preventing double counting.
   - **On-device/local processing**: Operations executed purely in the browser (via `public/static/local/`) never hit backend routes. For local operations, `updateDownloadLink()` in `public/static/script.js` fires `processing_completed` via `ffTrackGoogleAnalytics()`.
   - **Rule**: Exactly one `processing_completed` event is emitted per physical conversion.

2. **First-Party Internal Operational Log (`/admin/stats`)**:
   - `file_processed` is an internal telemetry beacon dispatched to `/api/track` and aggregated into SQLite/PostgreSQL for admin diagnostics.
   - It is NOT sent to GA4 and is preserved for complete backwards compatibility with the operational dashboard.

---

## 7. Checkout Intent vs. Authoritative Business Events

- **Client-Side Intent Telemetry (`checkout/static/checkout.js`)**:
  - `checkout_viewed`: User navigated to pricing/checkout view (observational intent).
  - `checkout_started`: User clicked purchase button and created an order session (observational intent).
  - `checkout_returned_success`: User redirected back from Stripe success return URL (observational UX signal, NOT purchase truth).
  - **Never treated as financial/purchase truth**.
- **Authoritative Business Event (`webhooks/product_grants.py`)**:
  - `purchase`: Standard GA4 ecommerce event emitted strictly by `apply_product_grant()` after provider signature verification, payment confirmation, and entitlement persistence.
  - Webhook retries are deduplicated via `payment_events` idempotency table.
  - Sensitive identifiers (`transaction_id`, `user_id`, order IDs) are excluded per privacy contract.

---

## 8. Guidelines for Implementation

### Backend Measurement Protocol (`public/scripts/ga4_mp.py`)
1. **Source of Truth**: Import definitions and sanitizers from `public/scripts/ga4_schema.py`.
2. **Authoritative Success/Failure**: Dispatch `processing_completed` with `processing_duration_ms` on successful jobs and `processing_failed` with `error_category` and `processing_duration_ms` on caught exceptions.
3. **Session Correlation**: Safely extract `client_id` (`_ga` cookie / UUID) from the request ContextVar without synthetic fabrication.
4. **Resilience & Observability**: Dispatches are non-blocking with 2.0s timeouts. Log reason codes (`disabled`, `no_client_id`, `success`, `rejected`, `network_failure`) without logging secrets or raw payloads.

### GA4 Configuration & Sync Tooling (`scripts/sync_ga4.py`)
1. **Schema-Driven**: `build_desired_state()` programmatically inspects `PARAMETER_DEFINITIONS` and `EVENT_DEFINITIONS` in `ga4_schema.py`.
2. **Zero Hardcoding**: Custom dimensions (`tool_name`, `file_type`, `error_category`), custom metrics (`processing_duration_ms`), and key events (`processing_completed`, `file_downloaded`) are derived automatically.
3. **Safe Execution**: `--dry-run` and `--check` are guaranteed read-only.
