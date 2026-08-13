"""Regression tests for scripts/fix_models.py's tar extraction guard (#76).

`_safe_extract` replaces a bare `tarfile.extractall()` (CVE-2007-4559): a
member whose path escapes the destination directory, or that isn't a plain
file/dir (symlink, hardlink, device), must be rejected rather than written.
"""
import tarfile

import pytest

from scripts.fix_models import _safe_extract


def _make_tar(tmp_path, add_member):
    tar_path = tmp_path / "test.tar"
    with tarfile.open(tar_path, "w") as tar:
        add_member(tar)
    return tar_path


def test_safe_extract_allows_well_behaved_members(tmp_path):
    src = tmp_path / "payload.txt"
    src.write_text("hello")
    tar_path = _make_tar(tmp_path, lambda tar: tar.add(src, arcname="model/payload.txt"))
    dest = tmp_path / "dest"
    dest.mkdir()

    with tarfile.open(tar_path) as tar:
        _safe_extract(tar, dest)

    assert (dest / "model" / "payload.txt").read_text() == "hello"


def test_safe_extract_rejects_path_traversal(tmp_path):
    def add_member(tar):
        info = tarfile.TarInfo(name="../../etc/passwd")
        info.size = 0
        tar.addfile(info)

    tar_path = _make_tar(tmp_path, add_member)
    dest = tmp_path / "dest"
    dest.mkdir()

    with tarfile.open(tar_path) as tar:
        with pytest.raises(ValueError, match="outside destination"):
            _safe_extract(tar, dest)

    assert not (tmp_path / "etc" / "passwd").exists()


def test_safe_extract_rejects_absolute_path(tmp_path):
    def add_member(tar):
        info = tarfile.TarInfo(name="/etc/passwd")
        info.size = 0
        tar.addfile(info)

    tar_path = _make_tar(tmp_path, add_member)
    dest = tmp_path / "dest"
    dest.mkdir()

    with tarfile.open(tar_path) as tar:
        with pytest.raises(ValueError, match="outside destination"):
            _safe_extract(tar, dest)


def test_safe_extract_rejects_symlink(tmp_path):
    def add_member(tar):
        info = tarfile.TarInfo(name="model/evil-link")
        info.type = tarfile.SYMTYPE
        info.linkname = "/etc/passwd"
        tar.addfile(info)

    tar_path = _make_tar(tmp_path, add_member)
    dest = tmp_path / "dest"
    dest.mkdir()

    with tarfile.open(tar_path) as tar:
        with pytest.raises(ValueError, match="non-regular member"):
            _safe_extract(tar, dest)
