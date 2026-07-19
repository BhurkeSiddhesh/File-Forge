"""Anonymous, server-side operation event logging (no client-side analytics).

Every file-processing operation — direct API handlers in main.py and workflow
pipeline steps — records one row in a local SQLite database: which operation
ran, whether it succeeded, how long the actual processing call took, and a
coarse country code taken from Cloudflare's ``CF-IPCountry`` request header
(no geolocation lookup). No file names, file contents, or IP addresses are
ever stored. The session id is a random UUID carried in a first-party cookie,
linked to nothing.

The database lives at ``data/events.db`` next to the app (override with the
``EVENT_DB_PATH`` env var). Logging must never break an operation: every
storage failure is swallowed and reported at WARNING level.
"""

import contextvars
import logging
import math
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Optional, Tuple

logger = logging.getLogger("file_forge.event_log")

_BASE_DIR = Path(__file__).resolve().parent.parent

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
CREATE INDEX IF NOT EXISTS idx_operation_events_ts ON operation_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_operation_events_op_ts ON operation_events (operation, timestamp);

-- Navigation / funnel events (page views + client-side funnel steps). Kept in a
-- separate table from operation_events so the two never contend and each stays
-- easy to reason about. Same privacy model: no PII, no IPs, no file names — just
-- a coarse stage, an optional short label (a page path or tool category), a
-- coarse country, and the anonymous session id used to stitch the funnel.
CREATE TABLE IF NOT EXISTS funnel_events (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp   TEXT    NOT NULL,
    event       TEXT    NOT NULL,
    label       TEXT,
    country     TEXT,
    session_id  TEXT
);
CREATE INDEX IF NOT EXISTS idx_funnel_events_ts ON funnel_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_funnel_events_ev_ts ON funnel_events (event, timestamp);
CREATE INDEX IF NOT EXISTS idx_funnel_events_sess ON funnel_events (session_id);
"""

# The only funnel events we store. Anything else a client POSTs is ignored, so
# the table can't be polluted by arbitrary event names. Order matters: it's the
# funnel from broadest (landed on any page) to narrowest (downloaded a result).
FUNNEL_EVENTS = ("page_view", "tool_open", "file_processed", "file_downloaded")
_LABEL_MAX = 120

_init_lock = threading.Lock()
_initialized_paths: set = set()

# (country, session_id) for the current request, set by the middleware in
# main.py so handlers and threadpool workers don't need a Request threaded
# through. contextvars survive `run_in_threadpool` but NOT raw
# threading.Thread workers — those must capture get_request_context() in the
# handler and pass country/session_id to log_event explicitly.
_request_context: contextvars.ContextVar = contextvars.ContextVar(
    "ff_event_context", default=None
)


def set_request_context(country: Optional[str], session_id: Optional[str]):
    return _request_context.set((country, session_id))


def reset_request_context(token) -> None:
    _request_context.reset(token)


def get_request_context() -> Tuple[Optional[str], Optional[str]]:
    return _request_context.get() or (None, None)


def _db_path() -> Path:
    return Path(os.environ.get("EVENT_DB_PATH") or str(_BASE_DIR / "data" / "events.db"))


def _connect(path: Path) -> sqlite3.Connection:
    key = str(path)
    if key not in _initialized_paths:
        with _init_lock:
            if key not in _initialized_paths:
                path.parent.mkdir(parents=True, exist_ok=True)
                conn = sqlite3.connect(path, timeout=5)
                try:
                    conn.execute("PRAGMA journal_mode=WAL")
                    conn.executescript(_SCHEMA)
                    conn.commit()
                finally:
                    conn.close()
                _initialized_paths.add(key)
    conn = sqlite3.connect(path, timeout=5)
    # WAL + synchronous=NORMAL is SQLite's recommended durable-enough mode: it
    # drops the per-commit fsync (the dominant cost of this write, which runs on
    # the event loop after each operation) at the price of losing at most the
    # last few analytics rows on an OS crash — fine for droppable event data.
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


# Exception messages routinely embed the temp-file path (which contains the
# original filename), so path-like tokens are stripped before storage or before
# an error detail is returned to the client. The lookbehind keeps mid-word
# slashes ("90/180/270") intact — only tokens that start a path are scrubbed.
_PATH_TOKEN = re.compile(r"(?:(?<=[\s:'\"=(,\[])|^)(?:[A-Za-z]:)?[\\/][^\s'\"]+")


def scrub_paths(text: str) -> str:
    """Replace path-like tokens (which can embed uploaded filenames) with <path>."""
    return _PATH_TOKEN.sub("<path>", text)


def sanitize_error(error) -> Optional[str]:
    if error is None:
        return None
    if isinstance(error, BaseException):
        text = f"{type(error).__name__}: {error}" if str(error) else type(error).__name__
    else:
        text = str(error)
    return scrub_paths(text)[:500]


def log_event(
    operation: str,
    *,
    success: bool,
    duration_ms: float,
    use_ai: bool = False,
    error=None,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
) -> None:
    """Record one operation event. Never raises."""
    ctx_country, ctx_session = get_request_context()
    if country is None:
        country = ctx_country
    if session_id is None:
        session_id = ctx_session
    try:
        conn = _connect(_db_path())
        try:
            conn.execute(
                "INSERT INTO operation_events"
                " (timestamp, operation, use_ai, success, duration_ms, error, country, session_id)"
                " VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    operation,
                    1 if use_ai else 0,
                    1 if success else 0,
                    int(duration_ms),
                    sanitize_error(error),
                    country,
                    session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.warning("Failed to record operation event for %s", operation, exc_info=True)


async def timed(operation: str, awaitable: Awaitable, use_ai: bool = False):
    """Await an operation call, logging its outcome and duration."""
    started = time.perf_counter()
    try:
        result = await awaitable
    except Exception as exc:
        log_event(
            operation,
            success=False,
            duration_ms=(time.perf_counter() - started) * 1000,
            use_ai=use_ai,
            error=exc,
        )
        raise
    log_event(
        operation,
        success=True,
        duration_ms=(time.perf_counter() - started) * 1000,
        use_ai=use_ai,
    )
    return result


def timed_call(
    operation: str,
    fn,
    *args,
    use_ai: bool = False,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
    **kwargs,
):
    """Synchronous counterpart of timed() for sync call sites and worker threads."""
    started = time.perf_counter()
    try:
        result = fn(*args, **kwargs)
    except Exception as exc:
        log_event(
            operation,
            success=False,
            duration_ms=(time.perf_counter() - started) * 1000,
            use_ai=use_ai,
            error=exc,
            country=country,
            session_id=session_id,
        )
        raise
    log_event(
        operation,
        success=True,
        duration_ms=(time.perf_counter() - started) * 1000,
        use_ai=use_ai,
        country=country,
        session_id=session_id,
    )
    return result


def log_funnel_event(
    event: str,
    *,
    label: Optional[str] = None,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
) -> bool:
    """Record one navigation/funnel event. Never raises.

    Returns True if the event was accepted (a known funnel stage) and a write was
    attempted, False if the event name is unknown and was ignored.
    """
    if event not in FUNNEL_EVENTS:
        return False
    ctx_country, ctx_session = get_request_context()
    if country is None:
        country = ctx_country
    if session_id is None:
        session_id = ctx_session
    if label is not None:
        label = str(label)[:_LABEL_MAX]
    try:
        conn = _connect(_db_path())
        try:
            conn.execute(
                "INSERT INTO funnel_events (timestamp, event, label, country, session_id)"
                " VALUES (?, ?, ?, ?, ?)",
                (
                    datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
                    event,
                    label,
                    country,
                    session_id,
                ),
            )
            conn.commit()
        finally:
            conn.close()
    except Exception:
        logger.warning("Failed to record funnel event %s", event, exc_info=True)
    return True


def query_funnel(since: Optional[str] = None, top: int = 15) -> dict:
    """Aggregate the navigation funnel for /admin/stats. `since` pre-normalized.

    Returns per-stage unique-session counts (with the drop-off between stages),
    plus the most-viewed pages and most-opened tool categories.
    """
    where = " WHERE timestamp >= ?" if since else ""
    params = [since] if since else []

    conn = _connect(_db_path())
    try:
        conn.row_factory = sqlite3.Row

        # Unique sessions reaching each funnel stage.
        stages = []
        prev = None
        for ev in FUNNEL_EVENTS:
            row = conn.execute(
                "SELECT COUNT(DISTINCT session_id) AS n FROM funnel_events"
                f"{where}{' AND' if where else ' WHERE'} event = ?",
                params + [ev],
            ).fetchone()
            n = row["n"] or 0
            # Conversion from the previous (broader) stage, e.g. of everyone who
            # opened a tool, what fraction reached a downloaded result.
            conv = round(n / prev, 4) if prev else None
            stages.append({"event": ev, "sessions": n, "from_previous_rate": conv})
            prev = n

        total_events = conn.execute(
            f"SELECT COUNT(*) AS n FROM funnel_events{where}", params
        ).fetchone()["n"] or 0

        def _by_label(event_name):
            return [
                {"label": r["label"] or "(none)", "count": r["n"]}
                for r in conn.execute(
                    "SELECT label, COUNT(*) AS n FROM funnel_events"
                    f"{where}{' AND' if where else ' WHERE'} event = ?"
                    " GROUP BY label ORDER BY n DESC, label LIMIT ?",
                    params + [event_name, top],
                )
            ]

        return {
            "total_events": total_events,
            "stages": stages,
            "top_pages": _by_label("page_view"),
            "top_tools_opened": _by_label("tool_open"),
        }
    finally:
        conn.close()


def normalize_since(since: str) -> str:
    """Normalize a user-supplied ISO date/datetime to the stored UTC format.

    Stored timestamps all share one fixed-width UTC ISO format, so a plain
    lexicographic ``>=`` in SQL is a correct chronological comparison.
    Raises ValueError on unparseable input.
    """
    dt = datetime.fromisoformat(since.strip().replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec="milliseconds")


def query_stats(since: Optional[str] = None) -> dict:
    """Aggregate stats for /admin/stats. `since` must be pre-normalized."""
    where = " WHERE timestamp >= ?" if since else ""
    params = [since] if since else []
    op_where = f"{where} AND operation = ?" if where else " WHERE operation = ?"

    conn = _connect(_db_path())
    try:
        conn.row_factory = sqlite3.Row
        operations = {}
        total = 0
        for row in conn.execute(
            "SELECT operation, COUNT(*) AS runs, SUM(success) AS successes,"
            f" AVG(duration_ms) AS avg_ms FROM operation_events{where}"
            " GROUP BY operation ORDER BY runs DESC, operation",
            params,
        ):
            runs = row["runs"]
            successes = row["successes"] or 0
            # p95 = the duration at the 95th-percentile rank of this op's runs
            offset = max(0, math.ceil(runs * 0.95) - 1)
            p95_row = conn.execute(
                f"SELECT duration_ms FROM operation_events{op_where}"
                " ORDER BY duration_ms LIMIT 1 OFFSET ?",
                params + [row["operation"], offset],
            ).fetchone()
            operations[row["operation"]] = {
                "runs": runs,
                "successes": successes,
                "failures": runs - successes,
                "success_rate": round(successes / runs, 4),
                "avg_duration_ms": round(row["avg_ms"], 1) if row["avg_ms"] is not None else None,
                "p95_duration_ms": p95_row[0] if p95_row else None,
            }
            total += runs
        top_countries = [
            {"country": r["country"] or "unknown", "events": r["n"]}
            for r in conn.execute(
                f"SELECT country, COUNT(*) AS n FROM operation_events{where}"
                " GROUP BY country ORDER BY n DESC, country LIMIT 10",
                params,
            )
        ]
        result = {
            "since": since,
            "total_events": total,
            "operations": operations,
            "top_countries": top_countries,
        }
    finally:
        conn.close()
    # Navigation funnel (page views + client funnel steps) alongside the
    # operation stats, so /admin/stats is a single call for the whole picture.
    result["funnel"] = query_funnel(since)
    return result
