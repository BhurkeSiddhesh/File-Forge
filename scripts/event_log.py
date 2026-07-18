"""Anonymous server-side operation event log (SQLite, no client-side tracking).

Records one row per file operation (success or failure) so the operator can
see run counts, success rates, durations, and a country breakdown via
GET /admin/stats. Privacy rules, enforced here:

- No file names, file contents, or IP addresses are ever stored.
  Error messages are scrubbed of path/filename-looking tokens before insert.
- ``country`` comes only from Cloudflare's ``CF-IPCountry`` request header
  (no geolocation lookup happens server-side).
- ``session_id`` is a random UUID from an anonymous cookie — no PII.

Storage is a self-contained SQLite file (stdlib ``sqlite3``, no ORM) at
``public/data/events.db`` by default, overridable via the ``EVENTS_DB_PATH``
environment variable. Logging must never break an operation: ``log_event``
swallows and logs its own failures.
"""

import logging
import os
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)

_DEFAULT_DB_PATH = Path(__file__).resolve().parent.parent / "data" / "events.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS operation_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    operation   TEXT    NOT NULL,
    use_ai      INTEGER NOT NULL DEFAULT 0,
    success     INTEGER NOT NULL,
    duration_ms INTEGER NOT NULL,
    error       TEXT,
    country     TEXT,
    session_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_operation_events_op_ts
    ON operation_events (operation, timestamp);
"""

# Anything that looks like a filesystem path or a filename with an extension —
# operation exceptions often embed the temp-file path, which must not be stored.
_PATH_RE = re.compile(r"[^\s'\"]*[\\/][^\s'\"]+")
_FILENAME_RE = re.compile(r"[\w.\-]+\.[A-Za-z0-9]{1,5}\b")

_MAX_ERROR_LEN = 500


def _db_path() -> Path:
    return Path(os.environ.get("EVENTS_DB_PATH") or _DEFAULT_DB_PATH)


def _connect() -> sqlite3.Connection:
    path = _db_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path), timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(_SCHEMA)
    return conn


def scrub_error(message: str) -> str:
    """Strip path/filename-looking tokens so file names never reach the DB."""
    scrubbed = _PATH_RE.sub("<path>", message)
    scrubbed = _FILENAME_RE.sub("<file>", scrubbed)
    return scrubbed[:_MAX_ERROR_LEN]


def log_event(
    operation: str,
    success: bool,
    duration_ms: int,
    use_ai: bool = False,
    error: Optional[str] = None,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Record one operation run. Never raises — an event-log failure must not
    turn a successful file operation into a 500."""
    try:
        with _connect() as conn:
            conn.execute(
                "INSERT INTO operation_events "
                "(timestamp, operation, use_ai, success, duration_ms, error, country, session_id) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(),
                    operation,
                    1 if use_ai else 0,
                    1 if success else 0,
                    int(duration_ms),
                    scrub_error(error) if error else None,
                    country.strip().upper()[:2] if country and country.strip() else None,
                    session_id,
                ),
            )
    except Exception:
        logger.exception("Failed to record operation event for %s", operation)


def _percentile(sorted_values, pct: float):
    if not sorted_values:
        return None
    idx = max(0, min(len(sorted_values) - 1, round(pct * (len(sorted_values) - 1))))
    return sorted_values[int(idx)]


def get_stats(since: Optional[datetime] = None) -> dict:
    """Aggregate stats for /admin/stats, optionally limited to events at or
    after ``since`` (naive datetimes are treated as UTC)."""
    params = ()
    where = ""
    if since is not None:
        if since.tzinfo is None:
            since = since.replace(tzinfo=timezone.utc)
        where = "WHERE timestamp >= ?"
        params = (since.astimezone(timezone.utc).isoformat(),)

    with _connect() as conn:
        rows = conn.execute(
            f"SELECT operation, use_ai, success, duration_ms FROM operation_events {where}",
            params,
        ).fetchall()
        country_rows = conn.execute(
            f"SELECT country, COUNT(*) AS n FROM operation_events {where}"
            " GROUP BY country ORDER BY n DESC",
            params,
        ).fetchall()

    by_operation = {}
    for operation, _use_ai, success, duration_ms in rows:
        entry = by_operation.setdefault(
            operation, {"count": 0, "success_count": 0, "durations": []}
        )
        entry["count"] += 1
        entry["success_count"] += int(success)
        entry["durations"].append(duration_ms)

    for entry in by_operation.values():
        durations = sorted(entry.pop("durations"))
        entry["success_rate"] = round(entry["success_count"] / entry["count"], 4)
        entry["avg_duration_ms"] = round(sum(durations) / len(durations), 1)
        entry["p95_duration_ms"] = _percentile(durations, 0.95)

    top_countries = [
        {"country": country or "unknown", "count": count}
        for country, count in country_rows[:10]
    ]

    return {
        "total_events": len(rows),
        "since": since.isoformat() if since else None,
        "by_operation": by_operation,
        "top_countries": top_countries,
    }
