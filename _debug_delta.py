"""Debug: replicate the 4-test TestPeriodDelta sequence in one process."""
import subprocess

ROOT = r"C:\Users\siddh\Desktop\Projects\file-forge-private"
PY = ROOT + r"\.venv\Scripts\python.exe"

SNIPPET = r'''
import os, sqlite3, sys, tempfile, logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

logging.basicConfig(level=logging.WARNING)
sys.path.insert(0, r"ROOTDIR")
sys.path.insert(0, r"ROOTDIR\public")

from scripts import event_log
import admin_stats


def fresh_db():
    db = Path(tempfile.mkdtemp()) / "events.db"
    os.environ["EVENT_DB_PATH"] = str(db)
    return db


# test_invalid_since_returns_none
fresh_db()
print("invalid:", admin_stats.query_period_delta("not-a-date"))

# test_future_since_returns_none
fresh_db()
future = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
print("future:", admin_stats.query_period_delta(future))

# test_counts_against_previous_window
db = fresh_db()
event_log.log_funnel_event("page_view", session_id="s1")
event_log.log_event("pdf_unlock", success=True, duration_ms=100, session_id="s1")
conn = sqlite3.connect(str(db))
print("ops:", conn.execute("SELECT * FROM operation_events").fetchall())
print("funnel:", conn.execute("SELECT * FROM funnel_events").fetchall())
conn.close()
since = (datetime.now(timezone.utc) - timedelta(days=1)).isoformat()
print("DELTA:", admin_stats.query_period_delta(since))
'''.replace("ROOTDIR", ROOT)


def run(ctx):
    proc = subprocess.run([PY, "-c", SNIPPET], cwd=ROOT,
                          capture_output=True, text=True, timeout=120)
    return {"artifact": {
        "exit": proc.returncode,
        "stdout": proc.stdout[-3000:],
        "stderr": proc.stderr[-3000:],
    }}
