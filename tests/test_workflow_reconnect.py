"""Dropped workflow streams remain recoverable through the shared job registry."""
from __future__ import annotations

import asyncio
import io
import json
import threading
from pathlib import Path

import pytest
from starlette.datastructures import UploadFile

import main


@pytest.fixture
def anyio_backend():
    return "asyncio"


def _sse_event(chunk) -> dict:
    if isinstance(chunk, bytes):
        chunk = chunk.decode()
    assert chunk.startswith("data: ")
    return json.loads(chunk[6:].strip())


async def _wait_for_job(job_id: str, timeout: float = 3.0) -> dict:
    deadline = asyncio.get_running_loop().time() + timeout
    while asyncio.get_running_loop().time() < deadline:
        entry = main.app.state.jobs.get(job_id)
        if entry and entry["status"] == "done":
            return entry
        await asyncio.sleep(0.01)
    raise AssertionError("workflow job did not reach a terminal state")


@pytest.mark.anyio
async def test_workflow_finishes_after_sse_consumer_disconnects(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    monkeypatch.setattr(main, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(main, "OUTPUT_DIR", outputs)

    started = threading.Event()
    finish = threading.Event()
    observed_input = {}

    def slow_rotate(input_path, output_dir, angle, pages, password):
        observed_input["path"] = Path(input_path)
        started.set()
        assert finish.wait(2), "test never released the workflow step"
        target = Path(output_dir) / "result_forgefiles.org.pdf"
        target.write_bytes(Path(input_path).read_bytes())
        return str(target)

    monkeypatch.setattr(main, "rotate_pdf", slow_rotate)
    upload = UploadFile(filename="shared.pdf", file=io.BytesIO(b"%PDF-1.4 test"))
    response = await main.execute_workflow(
        file=upload,
        steps=json.dumps([{"type": "rotate_pdf", "config": {"angle": 90}}]),
    )

    stream = response.body_iterator
    start = _sse_event(await anext(stream))
    assert start["event"] == "start"
    assert response.headers["X-FF-Job-ID"] == start["job_id"]
    await stream.aclose()  # simulate a dropped browser/mobile SSE connection

    assert await asyncio.to_thread(started.wait, 2)
    assert observed_input["path"].exists(), "disconnect deleted the active upload"
    pending = main.app.state.jobs.get(start["job_id"])
    assert pending["status"] == "pending"
    assert pending["progress"]["event"] == "step_start"

    finish.set()
    job = await _wait_for_job(start["job_id"])
    assert job["event"]["event"] == "complete"
    assert job["event"]["download_token"]
    assert not observed_input["path"].exists()
    result = main.app.state.downloads.resolve(job["event"]["download_token"], None)
    assert result is not None and result.exists()


@pytest.mark.anyio
async def test_workflow_failure_is_stable_after_disconnect(tmp_path, monkeypatch):
    uploads = tmp_path / "uploads"
    outputs = tmp_path / "outputs"
    uploads.mkdir()
    outputs.mkdir()
    monkeypatch.setattr(main, "UPLOAD_DIR", uploads)
    monkeypatch.setattr(main, "OUTPUT_DIR", outputs)

    started = threading.Event()
    finish = threading.Event()

    def failing_rotate(*_args):
        started.set()
        assert finish.wait(2)
        raise RuntimeError("deliberate workflow failure")

    monkeypatch.setattr(main, "rotate_pdf", failing_rotate)
    upload = UploadFile(filename="shared.pdf", file=io.BytesIO(b"%PDF-1.4 test"))
    response = await main.execute_workflow(
        file=upload,
        steps=json.dumps([{"type": "rotate_pdf", "config": {"angle": 90}}]),
    )
    stream = response.body_iterator
    start = _sse_event(await anext(stream))
    await stream.aclose()
    assert await asyncio.to_thread(started.wait, 2)
    finish.set()

    job = await _wait_for_job(start["job_id"])
    assert job["event"]["event"] == "error"
    assert "deliberate workflow failure" in job["event"]["detail"]


def test_workflow_client_polls_the_job_registry_after_stream_loss():
    source = (Path(__file__).parents[1] / "static" / "script.js").read_text(
        encoding="utf-8"
    )
    workflow = source[source.index("async function runWorkflow()") :]
    workflow = workflow[: workflow.index("const MIN_STEP_VISIBLE_MS")]
    assert "jobId = data.job_id" in workflow
    assert "pollJobStatus(jobId, statusText" in workflow
    assert "'workflow'" in workflow
