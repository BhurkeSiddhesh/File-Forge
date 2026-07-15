"""
Tests for security_utils.secure_filename.
"""
import pytest
from scripts.security_utils import secure_filename


def test_secure_filename_normal():
    """Normal filename passes through unchanged."""
    assert secure_filename("report.pdf") == "report.pdf"


def test_secure_filename_empty_string():
    """Empty string returns fallback name."""
    assert secure_filename("") == "unnamed_file"


def test_secure_filename_none_like_empty():
    """Whitespace-only string that becomes empty after strip returns fallback."""
    result = secure_filename("\x00\x01\x02")
    assert result == "unnamed_file"


def test_secure_filename_path_traversal_forward_slash():
    """Forward-slash path traversal is stripped to basename only."""
    assert secure_filename("../../etc/passwd") == "passwd"


def test_secure_filename_path_traversal_backslash():
    """Backslash path traversal (Windows-style) is stripped to basename only."""
    assert secure_filename("..\\..\\windows\\system32\\cmd.exe") == "cmd.exe"


def test_secure_filename_mixed_slashes():
    """Mixed slash path traversal is handled correctly."""
    assert secure_filename("foo/bar\\baz.txt") == "baz.txt"


def test_secure_filename_removes_newline():
    """Newline character (log injection) is removed from the filename."""
    result = secure_filename("evil\nfile.pdf")
    assert "\n" not in result
    assert result == "evilfile.pdf"


def test_secure_filename_removes_carriage_return():
    """Carriage return is removed."""
    result = secure_filename("evil\rfile.pdf")
    assert "\r" not in result


def test_secure_filename_removes_null_byte():
    """Null byte is removed."""
    result = secure_filename("file\x00.pdf")
    assert "\x00" not in result


def test_secure_filename_preserves_spaces():
    """Printable spaces are preserved (spaces are printable characters)."""
    result = secure_filename("my file.pdf")
    assert result == "my file.pdf"


def test_secure_filename_unicode():
    """Unicode printable characters are preserved."""
    result = secure_filename("文件.pdf")
    assert result == "文件.pdf"


def test_secure_filename_only_non_printable_chars_returns_fallback():
    """Filename consisting entirely of non-printable chars returns fallback."""
    result = secure_filename("\x00\x01\x1f")
    assert result == "unnamed_file"


def test_secure_filename_deep_path_traversal():
    """Very deep path is still reduced to the final basename."""
    assert secure_filename("a/b/c/d/e/target.docx") == "target.docx"
