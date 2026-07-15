from pathlib import Path
import os

def secure_filename(filename: str) -> str:
    """
    Sanitize a filename to prevent path traversal and log injection.

    1. Extracts the basename (removes directory components).
    2. Removes non-printable characters (including newlines) to prevent log injection.
    3. Ensures the filename is not empty.
    """
    if not filename:
        return "unnamed_file"

    # 1. Strip path components (Defense against Path Traversal)
    # Using Path.name handles both forward and backward slashes on Windows/Unix correctly
    # provided we use the correct pathlib logic.
    # Actually, Path(filename).name depends on the OS flavor of Path.
    # If the server is Linux, Path('C:\\foo.txt').name might be 'C:\\foo.txt'.
    # So we should handle both separators explicitly.
    filename = filename.replace("\\", "/")
    filename = Path(filename).name

    # 2. Remove non-printable characters (Defense against Log Injection)
    # This removes \n, \r, \t, \0, etc.
    clean_name = "".join(c for c in filename if c.isprintable())

    # 3. Fallback for empty result
    if not clean_name:
        return "unnamed_file"

    return clean_name
