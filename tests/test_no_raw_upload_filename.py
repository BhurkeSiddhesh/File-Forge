"""Guard: no module builds a filesystem path straight from a client filename.

`scripts/utils.py::process_uploaded_file()` did exactly that — `upload_dir /
file.filename` with no basename strip, no allowlist, no sandbox check (issue
#13). It was deleted rather than fixed, because `save_upload()` in `main.py`
already owns upload handling and applies all three.

The shape has now appeared twice, so this test makes it fail the suite instead
of a review. Every legitimate call site either goes through `save_upload()` or
sanitises first — `Path(name.replace("\\\\", "/")).name` / `secure_filename()` —
so the raw `<something> / <something>.filename` join is always a defect.
"""
import ast
from pathlib import Path

import pytest

PUBLIC_DIR = Path(__file__).resolve().parent.parent

# `.filename` attributes that carry an unsanitised, client-supplied name.
_CLIENT_NAME_ATTRS = {"filename"}


def _python_sources():
    # The test tree quotes the pattern in prose and fixtures; only application
    # code is in scope.
    return [
        path
        for path in sorted(PUBLIC_DIR.rglob("*.py"))
        if "tests" not in path.relative_to(PUBLIC_DIR).parts
    ]


def _raw_joins(tree):
    """Yield line numbers of `<expr> / <expr>.filename` divisions.

    A Path join is the only meaning `/` can have when the right operand is a
    `.filename` attribute — dividing by a name is not arithmetic.
    """
    for node in ast.walk(tree):
        if not isinstance(node, ast.BinOp) or not isinstance(node.op, ast.Div):
            continue
        right = node.right
        if isinstance(right, ast.Attribute) and right.attr in _CLIENT_NAME_ATTRS:
            yield node.lineno


@pytest.mark.parametrize(
    "source", _python_sources(), ids=lambda p: str(p.relative_to(PUBLIC_DIR))
)
def test_no_path_join_on_raw_client_filename(source):
    tree = ast.parse(source.read_text(encoding="utf-8"), filename=str(source))
    offenders = list(_raw_joins(tree))
    assert not offenders, (
        f"{source.relative_to(PUBLIC_DIR)} joins a raw client filename onto a "
        f"path at line(s) {offenders}. Route the upload through "
        f"main.save_upload(), or sanitise with secure_filename() first."
    )


def test_deleted_upload_helpers_stay_deleted():
    """The two dead helpers must not come back; see the module docstring."""
    from scripts import utils

    assert not hasattr(utils, "process_uploaded_file")
    assert not hasattr(utils, "cleanup_temp_file")
