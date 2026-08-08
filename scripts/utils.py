"""
Download-filename helpers for Forge Files, plus the shared headless-LibreOffice
conversion helper used by the Excel and PPT converters.

Deliberately scoped to naming and stateless conversion helpers — nothing here
touches uploads. This module used to also carry a ``process_uploaded_file()``
"common upload pattern" that wrote the raw, client-supplied ``file.filename``
into the upload directory — path traversal waiting for its first caller. Upload
handling belongs to ``save_upload()`` in ``main.py``, which has the extension
allowlist, the size cap and the sandbox check; build any shared upload helper on
that, not here.
"""
import logging
import re
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)

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

def try_font(size: int):
    """Load a scalable TrueType font at ``size``, falling back across fonts likely
    to exist on the deploy target before giving up.

    ``arial.ttf`` is a Windows font almost never present on Linux; without a
    fallback chain, ``ImageFont.load_default()`` silently returns a tiny fixed-size
    bitmap font that ignores ``size`` entirely.
    """
    from PIL import ImageFont

    for name in ("arial.ttf", "DejaVuSans.ttf", "Helvetica.ttf"):
        try:
            return ImageFont.truetype(name, size)
        except (OSError, IOError):
            continue
    return ImageFont.load_default()

def libreoffice_to_pdf(input_path, output_dir, timeout: int = 120):
    """Convert an office document to PDF using headless LibreOffice.

    LibreOffice is the reference renderer for Office formats, so it preserves
    the fidelity a pure-Python renderer can't (cell fill colors, fonts, merged
    cells, charts and conditional formatting for spreadsheets; slide layout,
    themes, gradients and fonts for presentations). It is an environment
    invariant on the deploy target (installed by the Dockerfile / self-healed by
    the deploy workflow), and already powers ``word_to_pdf``.

    Returns the Path LibreOffice produced ("<input stem>.pdf" in ``output_dir``)
    on success, or ``None`` when LibreOffice is unavailable or the conversion
    failed — so callers keep a pure-Python fallback and never hard-depend on it.

    A private per-call user-profile directory is passed via
    ``-env:UserInstallation`` so concurrent conversions don't contend on the
    shared ``~/.config/libreoffice`` profile lock.
    """
    import subprocess
    import tempfile

    input_file = Path(input_path)
    binary = shutil.which("libreoffice") or shutil.which("soffice")
    if binary is None:
        return None

    profile_dir = tempfile.mkdtemp(prefix="ff_lo_profile_")
    try:
        result = subprocess.run(
            [binary, "--headless",
             f"-env:UserInstallation=file://{profile_dir}",
             "--convert-to", "pdf",
             "--outdir", str(output_dir), str(input_file)],
            capture_output=True, text=True, timeout=timeout,
        )
        # LibreOffice writes "<input stem>.pdf" itself into --outdir.
        produced = Path(output_dir) / f"{input_file.stem}.pdf"
        if result.returncode == 0 and produced.exists():
            return produced
        logger.warning(
            "LibreOffice PDF conversion failed for %s (rc=%s): %s",
            input_file.name, result.returncode, (result.stderr or "").strip()[:200],
        )
        return None
    except Exception as exc:  # timeout, missing shared libs, etc. -> fall back
        logger.warning("LibreOffice PDF conversion errored for %s: %s", input_file.name, exc)
        return None
    finally:
        shutil.rmtree(profile_dir, ignore_errors=True)
