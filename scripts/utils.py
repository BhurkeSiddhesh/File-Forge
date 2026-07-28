"""
Download-filename helpers for Forge Files.

Deliberately scoped to naming only. This module used to also carry a
``process_uploaded_file()`` "common upload pattern" that wrote the raw,
client-supplied ``file.filename`` into the upload directory — path traversal
waiting for its first caller. Upload handling belongs to ``save_upload()`` in
``main.py``, which has the extension allowlist, the size cap and the sandbox
check; build any shared helper on that, not here.
"""
import re
from pathlib import Path

# Upload temp files are saved as "<uuid4>_<original_filename>" (see main.py); this
# strips that prefix back off so output filenames reflect what the user uploaded.
_UPLOAD_UUID_PREFIX_RE = re.compile(
    r'^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}_'
)

# A workflow step's output (already carrying this suffix) commonly becomes the
# next step's input, so stripping only the UUID prefix isn't enough — without
# also stripping a pre-existing brand suffix, re-branding stacks it every step
# ("sample_forgefiles.org_forgefiles.org...").
_BRAND_SUFFIX_RE = re.compile(r'_forgefiles\.org$', re.IGNORECASE)


def original_stem(input_path) -> str:
    """Return the uploaded file's original stem, with any temp-file UUID prefix
    and/or pre-existing brand suffix stripped (idempotent across chained steps)."""
    stem = _UPLOAD_UUID_PREFIX_RE.sub("", Path(input_path).stem)
    return _BRAND_SUFFIX_RE.sub("", stem)


def branded_filename(input_path, ext: str) -> str:
    """Build the public download filename: '<original name>_forgefiles.org.<ext>'."""
    return f"{original_stem(input_path)}_forgefiles.org.{ext.lstrip('.')}"
