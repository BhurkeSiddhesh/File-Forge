"""Unit tests for JobRegistry (issue #95): tracks a background SSE job's
terminal outcome by a stable job_id, independent of the SSE connection that
started it, so a client that reconnects after a dropped stream can recover a
result the server finished producing while nobody was listening."""
import time

import main


def test_create_returns_a_pending_job():
    registry = main.JobRegistry()
    job_id = registry.create()

    entry = registry.get(job_id)
    assert entry["status"] == "pending"


def test_set_result_marks_the_job_done():
    registry = main.JobRegistry()
    job_id = registry.create()
    registry.set_result(job_id, {"event": "complete", "download_token": "tok123"})

    entry = registry.get(job_id)
    assert entry["status"] == "done"
    assert entry["event"] == {"event": "complete", "download_token": "tok123"}


def test_get_returns_none_for_unknown_job():
    registry = main.JobRegistry()
    assert registry.get("never-created") is None


def test_set_result_on_an_unknown_job_id_does_not_raise():
    """Defensive: a job_id that was never created() (or already expired)
    shouldn't blow up the worker thread that's trying to report its result."""
    registry = main.JobRegistry()
    registry.set_result("phantom-job", {"event": "complete"})
    assert registry.get("phantom-job")["status"] == "done"


def test_get_expires_entries_past_file_ttl(monkeypatch):
    monkeypatch.setattr(main, "FILE_TTL_SECONDS", 100)
    registry = main.JobRegistry()
    job_id = registry.create()

    real_monotonic = time.monotonic
    monkeypatch.setattr(main.time, "monotonic", lambda: real_monotonic() + 200)

    assert registry.get(job_id) is None
