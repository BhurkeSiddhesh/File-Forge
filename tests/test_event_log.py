"""Tests for the server-side operation event log (scripts/event_log.py) and
the /admin/stats endpoint + handler instrumentation in main.py."""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

import os
import sqlite3
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch

from main import app
from scripts import event_log
from scripts.event_log import log_event, get_stats, scrub_error

ADMIN_KEY = "test-admin-stats-key"  # ggignore


@pytest.fixture
def events_db(tmp_path, monkeypatch):
    """Point the event log at a fresh temp SQLite file."""
    db_path = tmp_path / "events.db"
    monkeypatch.setenv("EVENTS_DB_PATH", str(db_path))
    return db_path


@pytest.fixture
def client():
    return TestClient(app)


# ──────────────────────────────────────────────────────────────
# scripts/event_log.py unit tests
# ──────────────────────────────────────────────────────────────

def test_log_event_writes_row(events_db):
    log_event("pdf_unlock", success=True, duration_ms=120, country="in", session_id="abc")
    rows = sqlite3.connect(str(events_db)).execute(
        "SELECT operation, use_ai, success, duration_ms, error, country, session_id "
        "FROM operation_events"
    ).fetchall()
    assert rows == [("pdf_unlock", 0, 1, 120, None, "IN", "abc")]


def test_log_event_never_raises(tmp_path, monkeypatch):
    # An unwritable DB path must not propagate an exception to the operation.
    blocker = tmp_path / "not_a_dir"
    blocker.write_text("plain file where a directory is needed")
    monkeypatch.setenv("EVENTS_DB_PATH", str(blocker / "sub" / "events.db"))
    log_event("pdf_unlock", success=True, duration_ms=1)  # must not raise


def test_error_scrubbing_strips_paths_and_filenames(events_db):
    log_event(
        "resize", success=False, duration_ms=5,
        error="cannot open /home/user/uploads/tax_return.pdf: bad header in report.docx",
    )
    (error,) = sqlite3.connect(str(events_db)).execute(
        "SELECT error FROM operation_events"
    ).fetchone()
    assert "tax_return" not in error
    assert "report.docx" not in error
    assert "<path>" in error or "<file>" in error


def test_scrub_error_truncates():
    assert len(scrub_error("x" * 2000)) == 500


def test_get_stats_aggregates(events_db):
    for duration in (100, 200, 300):
        log_event("crop", success=True, duration_ms=duration, country="IN")
    log_event("crop", success=False, duration_ms=400, error="boom", country="US")
    log_event("pdf_to_word_ai", success=True, duration_ms=1000, use_ai=True, country="US")

    stats = get_stats()
    assert stats["total_events"] == 5
    crop = stats["by_operation"]["crop"]
    assert crop["count"] == 4
    assert crop["success_count"] == 3
    assert crop["success_rate"] == 0.75
    assert crop["avg_duration_ms"] == 250.0
    assert crop["p95_duration_ms"] == 400
    assert stats["by_operation"]["pdf_to_word_ai"]["count"] == 1
    countries = {c["country"]: c["count"] for c in stats["top_countries"]}
    assert countries == {"IN": 3, "US": 2}


def test_get_stats_since_filter(events_db):
    log_event("crop", success=True, duration_ms=10)
    future = datetime.now(timezone.utc) + timedelta(days=1)
    assert get_stats(since=future)["total_events"] == 0
    past = datetime.now(timezone.utc) - timedelta(days=1)
    assert get_stats(since=past)["total_events"] == 1


# ──────────────────────────────────────────────────────────────
# /admin/stats endpoint
# ──────────────────────────────────────────────────────────────

def test_admin_stats_503_when_unconfigured(client, monkeypatch):
    monkeypatch.delenv("ADMIN_STATS_KEY", raising=False)
    assert client.get("/admin/stats").status_code == 503


def test_admin_stats_401_without_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_STATS_KEY", ADMIN_KEY)
    assert client.get("/admin/stats").status_code == 401


def test_admin_stats_401_with_wrong_token(client, monkeypatch):
    monkeypatch.setenv("ADMIN_STATS_KEY", ADMIN_KEY)
    resp = client.get("/admin/stats", headers={"Authorization": "Bearer wrong"})
    assert resp.status_code == 401


def test_admin_stats_200_with_valid_token(client, events_db, monkeypatch):
    monkeypatch.setenv("ADMIN_STATS_KEY", ADMIN_KEY)
    log_event("pdf_unlock", success=True, duration_ms=42, country="IN")
    resp = client.get("/admin/stats", headers={"Authorization": f"Bearer {ADMIN_KEY}"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_events"] == 1
    assert body["by_operation"]["pdf_unlock"]["success_rate"] == 1.0
    assert body["top_countries"] == [{"country": "IN", "count": 1}]


def test_admin_stats_400_on_bad_since(client, monkeypatch):
    monkeypatch.setenv("ADMIN_STATS_KEY", ADMIN_KEY)
    resp = client.get(
        "/admin/stats",
        params={"since": "not-a-date"},
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert resp.status_code == 400


def test_admin_stats_since_filters(client, events_db, monkeypatch):
    monkeypatch.setenv("ADMIN_STATS_KEY", ADMIN_KEY)
    log_event("pdf_unlock", success=True, duration_ms=42)
    tomorrow = (datetime.now(timezone.utc) + timedelta(days=1)).date().isoformat()
    resp = client.get(
        "/admin/stats",
        params={"since": tomorrow},
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
    )
    assert resp.status_code == 200
    assert resp.json()["total_events"] == 0


# ──────────────────────────────────────────────────────────────
# Handler instrumentation end-to-end
# ──────────────────────────────────────────────────────────────

@pytest.fixture
def mock_dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield


def _events(db_path):
    return sqlite3.connect(str(db_path)).execute(
        "SELECT operation, success, error, country, session_id FROM operation_events"
    ).fetchall()


def test_extract_pages_logs_event_and_sets_session_cookie(
    client, events_db, mock_dirs, multi_page_pdf
):
    with open(multi_page_pdf, "rb") as f:
        resp = client.post(
            "/api/pdf/extract-pages",
            files={"file": ("multi.pdf", f, "application/pdf")},
            data={"pages": "1-2"},
            headers={"CF-IPCountry": "IN"},
        )
    assert resp.status_code == 200
    assert "ff_session" in resp.cookies

    events = _events(events_db)
    assert len(events) == 1
    operation, success, error, country, session_id = events[0]
    assert operation == "page_extract"
    assert success == 1
    assert error is None
    assert country == "IN"
    assert session_id == resp.cookies["ff_session"]


def test_failed_operation_logs_failure_without_filename(client, events_db, mock_dirs):
    resp = client.post(
        "/api/pdf/extract-pages",
        files={"file": ("secret_taxes.pdf", b"not a real pdf", "application/pdf")},
        data={"pages": "1"},
    )
    assert resp.status_code == 400
    events = _events(events_db)
    assert len(events) == 1
    operation, success, error, country, _ = events[0]
    assert operation == "page_extract"
    assert success == 0
    assert error and "secret_taxes" not in error
    assert country is None


def test_session_cookie_is_reused_not_reminted(client, events_db, mock_dirs, multi_page_pdf):
    client.cookies.set("ff_session", "existing-session-id")
    with open(multi_page_pdf, "rb") as f:
        resp = client.post(
            "/api/pdf/extract-pages",
            files={"file": ("multi.pdf", f, "application/pdf")},
            data={"pages": "1"},
        )
    assert resp.status_code == 200
    assert "ff_session" not in resp.headers.get("set-cookie", "")
    assert _events(events_db)[0][4] == "existing-session-id"


def test_workflow_step_logs_by_step_name(client, events_db, mock_dirs, sample_pdf):
    with open(sample_pdf, "rb") as f:
        resp = client.post(
            "/api/workflow/execute",
            files={"file": ("sample.pdf", f, "application/pdf")},
            data={"steps": '[{"type": "rotate_pdf", "config": {"angle": 90}}]'},
            headers={"CF-IPCountry": "DE"},
        )
    assert resp.status_code == 200
    assert '"event": "complete"' in resp.text
    events = _events(events_db)
    assert len(events) == 1
    operation, success, _, country, _ = events[0]
    assert operation == "rotate_pdf"
    assert success == 1
    assert country == "DE"
