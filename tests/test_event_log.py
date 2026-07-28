"""Tests for the anonymous operation event log (scripts/event_log.py),
the request-context middleware, and handler instrumentation."""

import asyncio
import json
import sqlite3
import threading
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

# Note: /admin/stats tests moved to the private repo's tests/test_admin_stats.py
# alongside the route itself — see scripts/event_log.py's closing comment for why
# the aggregation/reporting side no longer lives in the public repo.


# --- funnel beacon: /api/track bot filtering ---

def _read_funnel(db):
    conn = sqlite3.connect(db)
    conn.row_factory = sqlite3.Row
    try:
        return [dict(r) for r in conn.execute("SELECT * FROM funnel_events ORDER BY id")]
    except sqlite3.OperationalError:
        # The schema is created lazily on the first write, so "no such table"
        # is the expected shape of "nothing was ever recorded".
        return []
    finally:
        conn.close()


def test_track_records_a_browser_beacon(event_db, auth_client):
    resp = auth_client.post(
        "/api/track",
        json={"event": "page_view", "label": "/pdf-to-word"},
        headers={"User-Agent": "Mozilla/5.0 (Macintosh) AppleWebKit/537.36 Chrome/120 Safari/537.36"},
    )
    assert resp.status_code == 204
    rows = _read_funnel(event_db)
    assert len(rows) == 1
    assert rows[0]["event"] == "page_view"
    assert rows[0]["label"] == "/pdf-to-word"


@pytest.mark.parametrize("ua", [
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
    "Mozilla/5.0 HeadlessChrome/120.0.0.0",
    "python-requests/2.31.0",
    "curl/8.4.0",
    "Mozilla/5.0 (X11; Linux x86_64) Chrome/120 Safari/537.36 Lighthouse",
    "UptimeRobot/2.0",
])
def test_track_drops_automated_clients(event_db, auth_client, ua):
    """A handful of fake sessions visibly skews the funnel rates on a site this
    young, so JS-executing bots must not reach the event log."""
    resp = auth_client.post(
        "/api/track",
        json={"event": "page_view", "label": "/"},
        headers={"User-Agent": ua},
    )
    # Still 204: an automated client shouldn't be able to tell it was filtered,
    # and a real browser must never see an error from a tracking beacon.
    assert resp.status_code == 204
    assert _read_funnel(event_db) == []


def test_track_without_a_user_agent_is_still_recorded(event_db, auth_client):
    """Absent UA is not evidence of a bot — don't silently drop real visitors."""
    resp = auth_client.post("/api/track", json={"event": "page_view", "label": "/"})
    assert resp.status_code == 204
    assert len(_read_funnel(event_db)) == 1


# ---------------------------------------------------------------------------
# The write path (issue #17)
#
# Every event used to open a connection, insert, commit and close it — and
# timed(), which wraps essentially every endpoint, did that synchronously on
# the asyncio event loop, stalling every *other* in-flight request too.
# ---------------------------------------------------------------------------

def test_writer_connection_is_reused_across_events(event_db):
    """One long-lived connection, not one per event."""
    event_log.close_connections()

    opened = []
    real_connect = sqlite3.connect

    def counting_connect(*args, **kwargs):
        opened.append(args[0])
        return real_connect(*args, **kwargs)

    with patch.object(event_log.sqlite3, "connect", side_effect=counting_connect):
        for i in range(25):
            event_log.log_event(f"op_{i}", success=True, duration_ms=1)

    assert len(read_rows(event_db)) == 25
    # One for the schema bootstrap, one for the writer. Not 25 (or 50).
    assert len(opened) <= 2, opened


def test_timed_does_not_write_on_the_event_loop(event_db):
    """timed() must hand the SQLite write to a worker thread."""
    writer_threads = []
    real_write = event_log._write

    def recording_write(*args, **kwargs):
        writer_threads.append(threading.current_thread())
        return real_write(*args, **kwargs)

    async def scenario():
        loop_thread = threading.current_thread()

        async def work():
            return "done"

        with patch.object(event_log, "_write", side_effect=recording_write):
            assert await event_log.timed("op_async", work()) == "done"
        return loop_thread

    loop_thread = asyncio.run(scenario())

    assert writer_threads, "no event was written"
    for t in writer_threads:
        assert t is not loop_thread, "SQLite write ran on the event loop"
    assert [r["operation"] for r in read_rows(event_db)] == ["op_async"]


def test_timed_logs_the_failure_off_the_loop_too(event_db):
    writer_threads = []
    real_write = event_log._write

    def recording_write(*args, **kwargs):
        writer_threads.append(threading.current_thread())
        return real_write(*args, **kwargs)

    async def scenario():
        loop_thread = threading.current_thread()

        async def boom():
            raise ValueError("nope")

        with patch.object(event_log, "_write", side_effect=recording_write):
            with pytest.raises(ValueError):
                await event_log.timed("op_fail", boom())
        return loop_thread

    loop_thread = asyncio.run(scenario())

    assert writer_threads
    for t in writer_threads:
        assert t is not loop_thread
    rows = read_rows(event_db)
    assert rows[0]["success"] == 0


def test_events_survive_concurrent_writers(event_db):
    """WAL + one serialized writer: no lost rows, no 'database is locked'."""
    errors = []

    def worker(n):
        try:
            for i in range(20):
                event_log.log_event(f"op_t{n}", success=True, duration_ms=i)
        except Exception as exc:  # pragma: no cover - the point is that it doesn't
            errors.append(exc)

    threads = [threading.Thread(target=worker, args=(n,)) for n in range(8)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len(read_rows(event_db)) == 8 * 20


def test_broken_connection_is_dropped_and_recovered(event_db):
    """A poisoned handle must not wedge every later event."""
    event_log.log_event("before", success=True, duration_ms=1)

    with event_log._writer_lock:
        event_log._writer[1].close()   # handle is now unusable

    # Swallowed, and the dead handle is dropped...
    event_log.log_event("during", success=True, duration_ms=1)
    # ...so the next event reopens and lands.
    event_log.log_event("after", success=True, duration_ms=1)

    ops = [r["operation"] for r in read_rows(event_db)]
    assert "before" in ops and "after" in ops
