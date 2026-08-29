import subprocess
import sys
from pathlib import Path
import pytest

# Put public/ on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.utils import original_stem, branded_filename, try_font, libreoffice_to_pdf


class TestUtils:
    def test_original_stem_various_patterns(self):
        assert original_stem("simple.pdf") == "simple"
        assert original_stem("/path/to/12345678-1234-1234-1234-123456789abc_document.docx") == "document"
        assert original_stem("document_forgefiles.org.pdf") == "document"
        assert original_stem("12345678-1234-1234-1234-123456789abc_doc_forgefiles.org.pdf") == "doc"

    def test_branded_filename(self):
        assert branded_filename("myfile.docx", "pdf") == "myfile_forgefiles.org.pdf"
        assert branded_filename("myfile.docx", ".pdf") == "myfile_forgefiles.org.pdf"
        assert branded_filename("12345678-1234-1234-1234-123456789abc_sample.pdf", "txt") == "sample_forgefiles.org.txt"

    def test_try_font(self):
        font = try_font(12)
        assert font is not None
        
        # Test fallback when TTF fonts are not found
        font_large = try_font(24)
        assert font_large is not None

    def test_libreoffice_to_pdf_not_installed(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: None)
        out = tmp_path / "out"
        out.mkdir()
        doc = tmp_path / "test.docx"
        doc.write_text("dummy")
        
        res = libreoffice_to_pdf(doc, out)
        assert res is None

    def test_libreoffice_to_pdf_success_simulation(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/libreoffice")
        out = tmp_path / "out"
        out.mkdir()
        doc = tmp_path / "test.docx"
        doc.write_text("dummy")
        
        def fake_run(cmd, capture_output, text, timeout):
            # simulate libreoffice creating test.pdf in output dir
            produced = out / "test.pdf"
            produced.write_text("%PDF-1.4 simulated")
            class Res:
                returncode = 0
                stderr = ""
            return Res()
            
        monkeypatch.setattr("subprocess.run", fake_run)
        res = libreoffice_to_pdf(doc, out)
        assert res == out / "test.pdf"
        assert res.exists()

    def test_libreoffice_to_pdf_locks_down_macros_and_recovery_flags(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/libreoffice")
        profile = tmp_path / "lo-profile"
        monkeypatch.setattr("tempfile.mkdtemp", lambda prefix: str(profile))
        monkeypatch.setattr("shutil.rmtree", lambda path, ignore_errors=True: None)

        out = tmp_path / "out"
        out.mkdir()
        doc = tmp_path / "macro.doc"
        doc.write_text("dummy")
        captured = {}

        def fake_run(cmd, capture_output, text, timeout):
            captured["cmd"] = cmd
            produced = out / "macro.pdf"
            produced.write_text("%PDF-1.4 simulated")
            class Res:
                returncode = 0
                stderr = ""
            return Res()

        monkeypatch.setattr("subprocess.run", fake_run)
        res = libreoffice_to_pdf(doc, out)

        assert res == out / "macro.pdf"
        registry = profile / "user" / "registrymodifications.xcu"
        assert registry.exists()
        xcu = registry.read_text(encoding="utf-8")
        assert 'oor:name="MacroSecurityLevel"' in xcu
        assert "<value>3</value>" in xcu

        cmd = captured["cmd"]
        assert "--headless" in cmd
        assert "--norestore" in cmd
        assert "--nolockcheck" in cmd
        assert "--nodefault" in cmd
        assert "--nologo" in cmd
        assert f"-env:UserInstallation={profile.resolve().as_uri()}" in cmd
        assert cmd[cmd.index("--convert-to") + 1] == "pdf"

    def test_libreoffice_to_pdf_subprocess_error(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/libreoffice")
        out = tmp_path / "out"
        out.mkdir()
        doc = tmp_path / "bad.docx"
        doc.write_text("dummy")
        
        def fake_run(cmd, capture_output, text, timeout):
            class Res:
                returncode = 1
                stderr = "Conversion error"
            return Res()
            
        monkeypatch.setattr("subprocess.run", fake_run)
        res = libreoffice_to_pdf(doc, out)
        assert res is None

    def test_libreoffice_to_pdf_exception_handling(self, tmp_path, monkeypatch):
        monkeypatch.setattr("shutil.which", lambda x: "/usr/bin/libreoffice")
        out = tmp_path / "out"
        out.mkdir()
        doc = tmp_path / "timeout.docx"
        doc.write_text("dummy")
        
        def fake_run(cmd, capture_output, text, timeout):
            raise subprocess.TimeoutExpired(cmd=cmd, timeout=timeout)
            
        monkeypatch.setattr("subprocess.run", fake_run)
        res = libreoffice_to_pdf(doc, out)
        assert res is None
