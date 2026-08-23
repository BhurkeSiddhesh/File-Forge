"""One-shot helper: run pytest files via the project venv and report tails."""
import subprocess

ROOT = r"C:\Users\siddh\Desktop\Projects\file-forge-private"
PY = ROOT + r"\.venv\Scripts\python.exe"

JOBS = [
    (ROOT, ["-m", "pytest",
            "tests/test_premium_full_coverage.py",
            "tests/test_admin_full_coverage.py",
            "tests/test_server_checkout_auth_coverage.py",
            "-q", "--no-header", "--tb=short"]),
]


def run(ctx):
    results = {}
    for cwd, args in JOBS:
        proc = subprocess.run(
            [PY] + args, cwd=cwd, capture_output=True, text=True, timeout=540
        )
        out = (proc.stdout or "") + "\n--- STDERR ---\n" + (proc.stderr or "")
        results[f"{cwd.split(chr(92))[-1]}::{args[2]}"] = {
            "exit": proc.returncode,
            "tail": out[-6000:],
        }
    return {"artifact": results}
