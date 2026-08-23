import sys
from pathlib import Path
import pytest
import pikepdf

# Put public/ on sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pdf_password_remover import remove_pdf_password, main
from scripts.pdf_utils import create_blank_pdf, protect_pdf


class TestPDFPasswordRemover:
    def test_remove_pdf_password_success(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        
        # Create a blank PDF and protect it
        blank = create_blank_pdf(str(out), num_pages=2)
        protected = protect_pdf(blank, str(out), user_password="secretpassword")
        
        # Test removing password
        unlocked = remove_pdf_password(protected, "secretpassword")
        assert Path(unlocked).exists()
        assert Path(unlocked).name.endswith("_unlocked.pdf")
        
        # Verify it can be opened without password
        with pikepdf.open(unlocked) as pdf:
            assert len(pdf.pages) == 2

    def test_remove_pdf_password_custom_output(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        
        blank = create_blank_pdf(str(out), num_pages=1)
        protected = protect_pdf(blank, str(out), user_password="pass")
        custom_out = out / "custom_unlocked.pdf"
        
        result = remove_pdf_password(protected, "pass", str(custom_out))
        assert result == str(custom_out)
        assert custom_out.exists()

    def test_remove_pdf_password_nonexistent_file(self, tmp_path):
        with pytest.raises(FileNotFoundError, match="Input file not found"):
            remove_pdf_password(str(tmp_path / "does_not_exist.pdf"), "pass")

    def test_remove_pdf_password_non_pdf_extension(self, tmp_path):
        txt_file = tmp_path / "document.txt"
        txt_file.write_text("hello")
        with pytest.raises(ValueError, match="Input file must be a PDF"):
            remove_pdf_password(str(txt_file), "pass")

    def test_remove_pdf_password_wrong_password(self, tmp_path):
        out = tmp_path / "out"
        out.mkdir()
        blank = create_blank_pdf(str(out), num_pages=1)
        protected = protect_pdf(blank, str(out), user_password="correct_pass")
        
        with pytest.raises(pikepdf.PasswordError):
            remove_pdf_password(protected, "wrong_pass")


class TestPDFPasswordRemoverCLI:
    def test_cli_single_file_success(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "out"
        out.mkdir()
        blank = create_blank_pdf(str(out), num_pages=1)
        protected = protect_pdf(blank, str(out), user_password="mypass")
        
        monkeypatch.setattr(sys, "argv", ["pdf_password_remover.py", protected, "mypass"])
        main()
        captured = capsys.readouterr()
        assert "Password removed successfully!" in captured.out

    def test_cli_single_file_nonexistent(self, tmp_path, monkeypatch, capsys):
        monkeypatch.setattr(sys, "argv", ["pdf_password_remover.py", str(tmp_path / "none.pdf"), "mypass"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error: Input file not found" in captured.out

    def test_cli_single_file_wrong_password(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "out"
        out.mkdir()
        blank = create_blank_pdf(str(out), num_pages=1)
        protected = protect_pdf(blank, str(out), user_password="realpass")
        
        monkeypatch.setattr(sys, "argv", ["pdf_password_remover.py", protected, "wrongpass"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Incorrect password" in captured.out

    def test_cli_interactive_input(self, tmp_path, monkeypatch, capsys):
        out = tmp_path / "out"
        out.mkdir()
        blank = create_blank_pdf(str(out), num_pages=1)
        protected = protect_pdf(blank, str(out), user_password="pass1")
        
        inputs = iter([f'"{protected}"', "pass1"])
        monkeypatch.setattr("builtins.input", lambda prompt="": next(inputs))
        monkeypatch.setattr(sys, "argv", ["pdf_password_remover.py"])
        main()
        captured = capsys.readouterr()
        assert "Password removed successfully!" in captured.out

    def test_cli_directory_batch(self, tmp_path, monkeypatch, capsys):
        batch_dir = tmp_path / "batch"
        batch_dir.mkdir()
        out_dir = tmp_path / "unlocked_batch"
        
        blank1 = create_blank_pdf(str(batch_dir), num_pages=1)
        blank2 = create_blank_pdf(str(batch_dir), num_pages=1)
        
        p1 = protect_pdf(blank1, str(batch_dir), user_password="batchpass")
        p2 = protect_pdf(blank2, str(batch_dir), user_password="batchpass")
        
        monkeypatch.setattr(
            sys, "argv",
            ["pdf_password_remover.py", str(batch_dir), "batchpass", "-o", str(out_dir)]
        )
        main()
        captured = capsys.readouterr()
        assert "Batch processing complete." in captured.out
        assert "Successful:" in captured.out

    def test_cli_directory_batch_with_errors(self, tmp_path, monkeypatch, capsys):
        batch_dir = tmp_path / "batch_errors"
        batch_dir.mkdir()
        blank1 = create_blank_pdf(str(batch_dir), num_pages=1)
        p1 = protect_pdf(blank1, str(batch_dir), user_password="pass1")
        
        # Corrupt one file
        bad_pdf = batch_dir / "bad.pdf"
        bad_pdf.write_text("not a real pdf")
        
        monkeypatch.setattr(
            sys, "argv",
            ["pdf_password_remover.py", str(batch_dir), "pass1"]
        )
        main()
        captured = capsys.readouterr()
        assert "Successful:" in captured.out
        assert "Failed:" in captured.out

    def test_cli_single_file_generic_error(self, tmp_path, monkeypatch, capsys):
        bad_pdf = tmp_path / "bad.pdf"
        bad_pdf.write_text("corrupted content")
        
        monkeypatch.setattr(sys, "argv", ["pdf_password_remover.py", str(bad_pdf), "anypass"])
        with pytest.raises(SystemExit) as exc:
            main()
        assert exc.value.code == 1
        captured = capsys.readouterr()
        assert "Error:" in captured.out

