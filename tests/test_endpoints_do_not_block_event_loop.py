"""Regression guard for issue #93: five endpoints called the CPU-heavy
conversion function directly (or via event_log.timed_call, its synchronous
counterpart) instead of dispatching through run_in_threadpool, so each one
monopolized the event loop for its full processing time -- stalling every
other in-flight request (health checks, other users' uploads, SSE ticks).

Mirrors the thread-identity technique test_event_log.py already uses for
event_log.timed(): call the handler coroutine directly via asyncio.run(),
capture which thread the conversion function actually executed on, and assert
it isn't the thread that ran the event loop.
"""
import asyncio
import io
import threading
from unittest.mock import patch

import pytest
from fastapi import UploadFile

import main


@pytest.fixture
def mock_dirs(tmp_path, monkeypatch):
    upload_dir = tmp_path / "uploads"
    output_dir = tmp_path / "outputs"
    upload_dir.mkdir()
    output_dir.mkdir()
    monkeypatch.setattr(main, "UPLOAD_DIR", upload_dir)
    monkeypatch.setattr(main, "OUTPUT_DIR", output_dir)
    return upload_dir, output_dir


def _fake_output(output_dir, name="out.bin"):
    p = output_dir / name
    p.write_bytes(b"fake output")
    return p


def test_remove_password_runs_off_the_event_loop(mock_dirs, tmp_path):
    upload_dir, output_dir = mock_dirs
    fake_output = _fake_output(output_dir)
    conversion_threads = []

    def fake_remove_pdf_password(*args, **kwargs):
        conversion_threads.append(threading.current_thread())
        return str(fake_output)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="doc.pdf", file=io.BytesIO(b"%PDF-1.4 dummy"))
        with patch.object(main, "remove_pdf_password", side_effect=fake_remove_pdf_password):
            result = await main.api_remove_password(file=upload, password="pw")
        return result, loop_thread

    result, loop_thread = asyncio.run(scenario())
    assert result["status"] == "success"
    assert conversion_threads, "remove_pdf_password was never called"
    for t in conversion_threads:
        assert t is not loop_thread, "remove_pdf_password ran on the event loop thread"


def test_convert_to_word_ai_branch_runs_off_the_event_loop(mock_dirs, tmp_path):
    upload_dir, output_dir = mock_dirs
    fake_output = _fake_output(output_dir, "out.docx")
    conversion_threads = []

    def fake_pdf_to_word_ai(*args, method_callback=None, **kwargs):
        conversion_threads.append(threading.current_thread())
        if method_callback:
            method_callback("ocr")
        return str(fake_output)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="doc.pdf", file=io.BytesIO(b"%PDF-1.4 dummy"))
        with patch.object(main, "pdf_to_word_ai", side_effect=fake_pdf_to_word_ai):
            result = await main.api_convert_to_word(file=upload, use_ai=True, password=None)
        return result, loop_thread

    result, loop_thread = asyncio.run(scenario())
    assert result["status"] == "success"
    assert conversion_threads, "pdf_to_word_ai was never called"
    for t in conversion_threads:
        assert t is not loop_thread, "pdf_to_word_ai ran on the event loop thread"


def test_heic_to_jpeg_runs_off_the_event_loop(mock_dirs, tmp_path):
    upload_dir, output_dir = mock_dirs
    fake_output = _fake_output(output_dir, "out.jpg")
    conversion_threads = []

    def fake_heic_to_jpeg(*args, **kwargs):
        conversion_threads.append(threading.current_thread())
        return str(fake_output)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="photo.heic", file=io.BytesIO(b"dummy heic bytes"))
        with patch.object(main, "heic_to_jpeg", side_effect=fake_heic_to_jpeg):
            result = await main.api_heic_to_jpeg(file=upload, quality=95)
        return result, loop_thread

    result, loop_thread = asyncio.run(scenario())
    assert result["status"] == "success"
    assert conversion_threads, "heic_to_jpeg was never called"
    for t in conversion_threads:
        assert t is not loop_thread, "heic_to_jpeg ran on the event loop thread"


def test_resize_image_runs_off_the_event_loop(mock_dirs, tmp_path):
    upload_dir, output_dir = mock_dirs
    fake_output = _fake_output(output_dir, "out.jpg")
    conversion_threads = []

    def fake_resize_image(*args, **kwargs):
        conversion_threads.append(threading.current_thread())
        return str(fake_output)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="photo.jpg", file=io.BytesIO(b"dummy jpg bytes"))
        with patch("scripts.image_utils.resize_image", side_effect=fake_resize_image):
            result = await main.api_resize_image(
                file=upload, mode="percentage", width=None, height=None,
                percentage=50, target_size_kb=None,
            )
        return result, loop_thread

    result, loop_thread = asyncio.run(scenario())
    assert result["status"] == "success"
    assert conversion_threads, "resize_image was never called"
    for t in conversion_threads:
        assert t is not loop_thread, "resize_image ran on the event loop thread"


def test_crop_image_runs_off_the_event_loop(mock_dirs, tmp_path):
    upload_dir, output_dir = mock_dirs
    fake_output = _fake_output(output_dir, "out.jpg")
    conversion_threads = []

    def fake_crop_image(*args, **kwargs):
        conversion_threads.append(threading.current_thread())
        return str(fake_output)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="photo.jpg", file=io.BytesIO(b"dummy jpg bytes"))
        with patch("scripts.image_utils.crop_image", side_effect=fake_crop_image):
            result = await main.api_crop_image(file=upload, x=0, y=0, width=10, height=10)
        return result, loop_thread

    result, loop_thread = asyncio.run(scenario())
    assert result["status"] == "success"
    assert conversion_threads, "crop_image was never called"
    for t in conversion_threads:
        assert t is not loop_thread, "crop_image ran on the event loop thread"


def test_save_upload_streams_to_disk_off_the_event_loop(mock_dirs):
    """save_upload()/_stream_to_disk() back every upload-accepting endpoint
    (issue #92); the disk write must not happen on the event loop thread."""
    write_threads = []
    real_stream = main._stream_to_disk

    def recording_stream(*args, **kwargs):
        write_threads.append(threading.current_thread())
        return real_stream(*args, **kwargs)

    async def scenario():
        loop_thread = threading.current_thread()
        upload = UploadFile(filename="doc.pdf", file=io.BytesIO(b"%PDF-1.4 dummy"))
        with patch.object(main, "_stream_to_disk", side_effect=recording_stream):
            dest = await main.save_upload(upload, main.PDF_EXTENSIONS)
        return dest, loop_thread

    dest, loop_thread = asyncio.run(scenario())
    assert dest.exists()
    assert write_threads, "_stream_to_disk was never called"
    for t in write_threads:
        assert t is not loop_thread, "upload disk write ran on the event loop thread"
