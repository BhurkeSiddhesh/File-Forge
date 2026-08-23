import io
import sys
import tarfile
from pathlib import Path
import pytest

# Put public/ on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.fix_models import download_and_extract, convert_to_onnx, _safe_extract


class TestFixModels:
    def test_safe_extract_rejects_non_regular_file(self, tmp_path):
        tar_path = tmp_path / "test.tar"
        out_dir = tmp_path / "out"
        out_dir.mkdir()
        
        # Create a tar with a FIFO or non-regular member
        tarinfo = tarfile.TarInfo(name="fifo_dev")
        tarinfo.type = tarfile.FIFOTYPE
        
        with tarfile.open(tar_path, "w") as tar:
            tar.addfile(tarinfo)
            
        with tarfile.open(tar_path, "r") as tar:
            with pytest.raises(ValueError, match="Refusing to extract non-regular member"):
                _safe_extract(tar, out_dir)

    def test_download_and_extract_already_exists(self, tmp_path, capsys):
        model_dir = tmp_path / "test_model"
        model_dir.mkdir(parents=True)
        (model_dir / "inference.pdmodel").write_text("dummy model")
        
        info = {
            "name": "test_model",
            "dir": tmp_path,
            "url": "http://dummy.url/model.tar"
        }
        res = download_and_extract("test", info)
        assert res == model_dir
        captured = capsys.readouterr()
        assert "already exists" in captured.out

    def test_download_and_extract_successful_flow(self, tmp_path, monkeypatch, capsys):
        dest_dir = tmp_path / "dest"
        dest_dir.mkdir()
        
        # Create a valid in-memory tar with a dummy pdmodel file
        tar_bytes_io = io.BytesIO()
        with tarfile.open(fileobj=tar_bytes_io, mode="w") as tar:
            content = b"fake pdmodel data"
            ti = tarfile.TarInfo(name="dummy_model/inference.pdmodel")
            ti.size = len(content)
            tar.addfile(ti, io.BytesIO(content))
        tar_bytes = tar_bytes_io.getvalue()
        
        class FakeResponse:
            def raise_for_status(self):
                pass
            def iter_content(self, chunk_size=8192):
                yield tar_bytes
                
        monkeypatch.setattr("requests.get", lambda url, stream, timeout: FakeResponse())
        
        info = {
            "name": "dummy_model",
            "dir": dest_dir,
            "url": "http://example.com/dummy.tar"
        }
        res = download_and_extract("dummy", info)
        assert res == dest_dir / "dummy_model"
        assert (dest_dir / "dummy_model" / "inference.pdmodel").exists()

    def test_download_and_extract_network_failure(self, tmp_path, monkeypatch, capsys):
        dest_dir = tmp_path / "dest_fail"
        dest_dir.mkdir()
        
        def fake_get(url, stream, timeout):
            raise ConnectionError("Network down")
            
        monkeypatch.setattr("requests.get", fake_get)
        
        info = {
            "name": "fail_model",
            "dir": dest_dir,
            "url": "http://example.com/fail.tar"
        }
        res = download_and_extract("fail", info)
        assert res is None
        captured = capsys.readouterr()
        assert "Failed to download/extract" in captured.out

    def test_convert_to_onnx_empty_or_missing(self, tmp_path, capsys):
        # When model_dir is None
        convert_to_onnx(None)
        
        # When model_dir has no .pdmodel
        empty_dir = tmp_path / "empty_model"
        empty_dir.mkdir()
        convert_to_onnx(empty_dir)
        captured = capsys.readouterr()
        assert "No .pdmodel found" in captured.out

    def test_convert_to_onnx_already_exists(self, tmp_path, capsys):
        model_dir = tmp_path / "existing_onnx"
        model_dir.mkdir()
        (model_dir / "model.pdmodel").write_text("pdmodel")
        (model_dir / "model.onnx").write_text("onnx")
        
        convert_to_onnx(model_dir)
        captured = capsys.readouterr()
        assert "ONNX model already exists" in captured.out

    def test_convert_to_onnx_run_subprocess(self, tmp_path, monkeypatch, capsys):
        model_dir = tmp_path / "convert_model"
        model_dir.mkdir()
        (model_dir / "inference.pdmodel").write_text("pdmodel")
        (model_dir / "inference.pdiparams").write_text("params")
        
        def fake_run(cmd, check, capture_output, env, text):
            # Create onnx file to simulate success
            (model_dir / "model.onnx").write_text("fake onnx")
            
        monkeypatch.setattr("subprocess.run", fake_run)
        convert_to_onnx(model_dir)
        captured = capsys.readouterr()
        assert "Conversion successful" in captured.out

    def test_convert_to_onnx_subprocess_error(self, tmp_path, monkeypatch, capsys):
        import subprocess
        model_dir = tmp_path / "convert_fail"
        model_dir.mkdir()
        (model_dir / "inference.pdmodel").write_text("pdmodel")
        (model_dir / "inference.pdiparams").write_text("params")
        
        def fake_run_fail(cmd, check, capture_output, env, text):
            raise subprocess.CalledProcessError(returncode=1, cmd=cmd, output="err stdout", stderr="err stderr")
            
        monkeypatch.setattr("subprocess.run", fake_run_fail)
        convert_to_onnx(model_dir)
        captured = capsys.readouterr()
        assert "Conversion failed" in captured.out

