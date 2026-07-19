"""Tests for the anonymous operation event log (scripts/event_log.py),
the request-context middleware, handler instrumentation, and /admin/stats."""

import asyncio
import json
import sqlite3
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from main import app
from scripts import event_log


@pytest.fixture
def event_db(tmp_path, monkeypatch):
    """Point the event log at a fresh temp DB for each test."""
    db = tmp_path / "events.db"
    monkeypatch.setenv("EVENT_DB_PATH", str(db))
    return db


@pytest.fixture
def mock_dirs(tmp_path):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    with patch("main.UPLOAD_DIR", upload_dir), patch("main.OUTPUT_DIR", output_dir):
        yield {"upload": upload_dir, "output": output_dir}


def read_rows(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM operation_events ORDER BY id")]
    finally:
        conn.close()


# --- unit: log_event / sanitize_error / timed ---

def test_log_event_writes_row(event_db):
    event_log.log_event(
        "pdf_unlock", success=True, duration_ms=123.7, country="IN", session_id="abc"
    )
    rows = read_rows(event_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["operation"] == "pdf_unlock"
    assert row["success"] == 1
    assert row["use_ai"] == 0
    assert row["duration_ms"] == 123
    assert row["error"] is None
    assert row["country"] == "IN"
    assert row["session_id"] == "abc"
    assert row["timestamp"].endswith("+00:00")  # stored in UTC


def test_sanitize_error_strips_paths():
    err = ValueError("cannot open /uploads/abc123_secret-report.pdf: bad password")
    text = event_log.sanitize_error(err)
    assert text.startswith("ValueError:")
    assert "secret-report" not in text
    assert "<path>" in text
    assert event_log.sanitize_error(None) is None


def test_scrub_paths_keeps_non_path_slashes():
    assert event_log.scrub_paths("angle must be 90/180/270") == "angle must be 90/180/270"
    assert event_log.scrub_paths("/uploads/abc_x.pdf: invalid password") == "<path> invalid password"
    assert (
        event_log.scrub_paths(r"cannot open C:\uploads\abc_x.pdf here")
        == "cannot open <path> here"
    )


def test_timed_logs_success_and_failure(event_db):
    async def ok():
        return "done"

    async def boom():
        raise RuntimeError("kaput")

    assert asyncio.run(event_log.timed("op_a", ok())) == "done"
    with pytest.raises(RuntimeError):
        asyncio.run(event_log.timed("op_a", boom()))

    rows = read_rows(event_db)
    assert [r["success"] for r in rows] == [1, 0]
    assert rows[1]["error"] == "RuntimeError: kaput"


def test_timed_call_reraises_and_logs(event_db):
    def boom():
        raise ValueError("nope")

    with pytest.raises(ValueError):
        event_log.timed_call("op_b", boom, country="US", session_id="s1")
    rows = read_rows(event_db)
    assert rows[0]["success"] == 0
    assert rows[0]["country"] == "US"
    assert rows[0]["session_id"] == "s1"


def test_logging_failure_never_raises(tmp_path, monkeypatch):
    # Unwritable DB path (parent "dir" is a regular file): the write fails,
    # the operation must not.
    blocker = tmp_path / "blocker"
    blocker.write_text("not a directory")
    monkeypatch.setenv("EVENT_DB_PATH", str(blocker / "sub" / "events.db"))
    event_log.log_event("op_c", success=True, duration_ms=1)


# --- integration: middleware + handler instrumentation ---

def test_api_operation_logged_with_country_and_session(event_db, mock_dirs, auth_client):
    resp = auth_client.post(
        "/api/pdf/create-blank",
        data={"num_pages": 1},
        headers={"cf-ipcountry": "IN"},
    )
    assert resp.status_code == 200
    assert "ff_sid" in resp.cookies

    rows = read_rows(event_db)
    assert len(rows) == 1
    row = rows[0]
    assert row["operation"] == "pdf_create_blank"
    assert row["success"] == 1
    assert row["country"] == "IN"
    assert row["session_id"] == resp.cookies["ff_sid"]


def test_session_id_persists_across_requests(event_db, mock_dirs, auth_client):
    auth_client.post("/api/pdf/create-blank", data={"num_pages": 1})
    auth_client.post("/api/pdf/create-blank", data={"num_pages": 1})
    rows = read_rows(event_db)
    assert len(rows) == 2
    assert rows[0]["session_id"] == rows[1]["session_id"]


def test_failure_logged_without_filename(event_db, mock_dirs, auth_client, locked_pdf):
    with open(locked_pdf["path"], "rb") as f:
        resp = auth_client.post(
            "/api/pdf/remove-password",
            files={"file": ("locked.pdf", f, "application/pdf")},
            data={"password": "definitely-wrong"},
        )
    assert resp.status_code == 400
    # The HTTP error detail must not leak the server temp path / filename either.
    assert "locked.pdf" not in resp.json()["detail"]
    assert "uploads" not in resp.json()["detail"]
    rows = read_rows(event_db)
    assert len(rows) == 1
    assert rows[0]["operation"] == "pdf_unlock"
    assert rows[0]["success"] == 0
    assert rows[0]["error"]
    assert "locked.pdf" not in rows[0]["error"]


def test_workflow_step_logged(event_db, mock_dirs, auth_client, locked_pdf):
    steps = json.dumps([
        {"type": "remove_password", "config": {"password": locked_pdf["password"]}}
    ])
    with open(locked_pdf["path"], "rb") as f:
        resp = auth_client.post(
            "/api/workflow/execute",
            files={"file": ("locked.pdf", f, "application/pdf")},
            data={"steps": steps},
        )
    assert resp.status_code == 200
    assert "step_complete" in resp.text

    rows = read_rows(event_db)
    assert len(rows) == 1
    assert rows[0]["operation"] == "remove_password"
    assert rows[0]["success"] == 1
    # The 1s artificial UI delay must not be counted in the step duration.
    assert rows[0]["duration_ms"] < 1000


def test_workflow_malformed_config_yields_clean_error(event_db, mock_dirs, auth_client, sample_pdf):
    # A non-dict `config` makes the operation raise; the failure must still be
    # logged and surface as a clean SSE error event, not crash the stream.
    steps = json.dumps([{"type": "resize_image", "config": "not-a-dict"}])
    with open(sample_pdf, "rb") as f:
        resp = auth_client.post(
            "/api/workflow/execute",
            files={"file": ("sample.pdf", f, "application/pdf")},
            data={"steps": steps},
        )
    assert resp.status_code == 200
    assert '"event": "error"' in resp.text
    rows = read_rows(event_db)
    assert len(rows) == 1
    assert rows[0]["operation"] == "resize_image"
    assert rows[0]["success"] == 0


# --- /admin/stats ---

def _seed_events():
    for duration, ok, country in ((100, True, "IN"), (200, True, "IN"), (300, False, "US")):
        event_log.log_event(
            "pdf_unlock", success=ok, duration_ms=duration, country=country, session_id="s"
        )
    for duration in (50, 60):
        event_log.log_event("resize", success=True, duration_ms=duration, session_id="s")


def test_admin_stats_unconfigured_returns_503(event_db, monkeypatch, auth_client):
    monkeypatch.delenv("ADMIN_STATS_KEY", raising=False)
    assert auth_client.get("/admin/stats").status_code == 503


def test_admin_stats_requires_bearer_token(event_db, monkeypatch, auth_client):
    monkeypatch.setenv("ADMIN_STATS_KEY", "test-admin-key")
    assert auth_client.get("/admin/stats").status_code == 401
    assert (
        auth_client.get("/admin/stats", headers={"Authorization": "Bearer wrong"}).status_code
        == 401
    )


def test_admin_stats_aggregates(event_db, monkeypatch, auth_client):
    monkeypatch.setenv("ADMIN_STATS_KEY", "test-admin-key")
    _seed_events()
    resp = auth_client.get(
        "/admin/stats", headers={"Authorization": "Bearer test-admin-key"}
    )
    assert resp.status_code == 200
    stats = resp.json()

    assert stats["total_events"] == 5
    unlock = stats["operations"]["pdf_unlock"]
    assert unlock["runs"] == 3
    assert unlock["successes"] == 2
    assert unlock["failures"] == 1
    assert unlock["success_rate"] == pytest.approx(2 / 3, abs=1e-3)
    assert unlock["avg_duration_ms"] == pytest.approx(200.0)
    assert unlock["p95_duration_ms"] == 300
    assert stats["operations"]["resize"]["runs"] == 2

    countries = {c["country"]: c["events"] for c in stats["top_countries"]}
    assert countries == {"IN": 2, "US": 1, "unknown": 2}


def test_admin_stats_since_filter(event_db, monkeypatch, auth_client):
    monkeypatch.setenv("ADMIN_STATS_KEY", "test-admin-key")
    _seed_events()
    headers = {"Authorization": "Bearer test-admin-key"}

    resp = auth_client.get("/admin/stats?since=2099-01-01", headers=headers)
    assert resp.status_code == 200
    assert resp.json()["total_events"] == 0

    resp = auth_client.get("/admin/stats?since=2020-01-01T00:00:00Z", headers=headers)
    assert resp.json()["total_events"] == 5

    assert (
        auth_client.get("/admin/stats?since=not-a-date", headers=headers).status_code == 400
    )
