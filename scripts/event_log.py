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

import asyncio
import contextvars
import logging
import os
import re
import sqlite3
import threading
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Awaitable, Optional, Tuple
from urllib.parse import urlsplit

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
    session_id  TEXT,
    -- Size of the request body that carried the input file(s), from the
    -- Content-Length header. A close upper bound on the input size (it also
    -- counts multipart boundaries and the other form fields), never the file's
    -- name or contents. NULL when the size wasn't known — non-upload
    -- operations, and every row written before this column existed.
    request_bytes INTEGER
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
    session_id  TEXT,
    -- Where the visitor came from, as a bare host ('google.com') or one of the
    -- fixed sentinels below. Never a full referring URL — a URL can carry the
    -- search query, and a query string is the one part of a referrer that can
    -- identify a person. NULL on every non-page_view row and on every row
    -- written before this column existed.
    referrer    TEXT
);
CREATE INDEX IF NOT EXISTS idx_funnel_events_ts ON funnel_events (timestamp);
CREATE INDEX IF NOT EXISTS idx_funnel_events_ev_ts ON funnel_events (event, timestamp);
CREATE INDEX IF NOT EXISTS idx_funnel_events_sess ON funnel_events (session_id);
"""

# Columns added after the tables above first shipped. CREATE TABLE IF NOT EXISTS
# leaves an existing table alone, so a database created before a column was
# added never gets it from _SCHEMA — these ALTERs are what actually migrate the
# production DB. Adding a nullable column is instant in SQLite (metadata-only)
# and old rows read back as NULL, which is exactly what "we didn't record this
# back then" should look like.
_ADDED_COLUMNS = (
    ("operation_events", "request_bytes", "INTEGER"),
    ("funnel_events", "referrer", "TEXT"),
)

# The only funnel events we store. Anything else a client POSTs is ignored, so
# the table can't be polluted by arbitrary event names. Order matters: it's the
# funnel from broadest (landed on any page) to narrowest (downloaded a result / purchase).
FUNNEL_EVENTS = (
    "page_view",
    "tool_open",
    "file_processed",
    "file_downloaded",
    "checkout_viewed",
    "checkout_started",
    "purchase_completed",
)
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

# Upload size for the current request, kept in its own contextvar rather than
# widened into the tuple above: several call sites unpack that tuple as a pair,
# and a metric is not worth breaking them for.
_request_bytes: contextvars.ContextVar = contextvars.ContextVar(
    "ff_event_request_bytes", default=None
)


def set_request_context(country: Optional[str], session_id: Optional[str]):
    return _request_context.set((country, session_id))


def reset_request_context(token) -> None:
    _request_context.reset(token)


def get_request_context() -> Tuple[Optional[str], Optional[str]]:
    return _request_context.get() or (None, None)


def set_request_bytes(size: Optional[int]):
    """Record how large the current request body is, for the events it produces."""
    return _request_bytes.set(size)


def reset_request_bytes(token) -> None:
    _request_bytes.reset(token)


def get_request_bytes() -> Optional[int]:
    return _request_bytes.get()


def _db_path() -> Path:
    return Path(os.environ.get("EVENT_DB_PATH") or str(_BASE_DIR / "data" / "events.db"))


def _ensure_schema(path: Path) -> None:
    key = str(path)
    if key in _initialized_paths:
        return
    with _init_lock:
        if key in _initialized_paths:
            return
        path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(path, timeout=5)
        try:
            conn.execute("PRAGMA journal_mode=WAL")
            conn.executescript(_SCHEMA)
            _migrate_columns(conn)
            conn.commit()
        finally:
            conn.close()
        _initialized_paths.add(key)


def _migrate_columns(conn: sqlite3.Connection) -> None:
    """Add any column in _ADDED_COLUMNS that this database doesn't have yet."""
    for table, column, decl in _ADDED_COLUMNS:
        existing = {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}
        if column in existing:
            continue
        # Never fatal: an unmigrated column only costs us one metric, whereas a
        # raising _ensure_schema would take the whole app down at startup.
        try:
            conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {decl}")
        except sqlite3.OperationalError:
            logger.warning("Could not add %s.%s to the event log", table, column, exc_info=True)


def _connect(path: Path) -> sqlite3.Connection:
    """Open a fresh connection. Used for reads; writes go through _write()."""
    _ensure_schema(path)
    conn = sqlite3.connect(path, timeout=5)
    # WAL + synchronous=NORMAL is SQLite's recommended durable-enough mode: it
    # drops the per-commit fsync at the price of losing at most the last few
    # analytics rows on an OS crash — fine for droppable event data.
    conn.execute("PRAGMA synchronous=NORMAL")
    return conn


def get_connection() -> sqlite3.Connection:
    """Open a connection to the event-log DB, for reporting/aggregation code
    that lives outside this module (e.g. the private deployment's admin
    endpoint). Plain plumbing — this module only ever writes; it has no
    aggregation logic of its own."""
    return _connect(_db_path())


# --- The write path ---
#
# Every event used to open a connection, insert, commit and close it — one
# connection setup plus a disk commit in the hot path of every API call, and
# (via timed()) directly on the asyncio event loop, where it stalled *every*
# concurrent request rather than just the one being logged. The `PRAGMA
# synchronous=NORMAL` was re-executed on each new handle for good measure.
#
# WAL supports one writer with concurrent readers, so a single long-lived write
# connection serialized by a lock is the natural shape: the connect/close and
# the repeated PRAGMA disappear, and the remaining cost is the insert itself.
# check_same_thread=False is safe precisely because _writer_lock serializes
# every use — log_event is called from threadpool workers and raw worker
# threads alike.
_writer_lock = threading.Lock()
_writer: Optional[Tuple[str, sqlite3.Connection]] = None


def _writer_connection(path: Path) -> sqlite3.Connection:
    """The shared write connection for `path`. Caller must hold _writer_lock."""
    global _writer
    key = str(path)
    if _writer is not None and _writer[0] == key:
        return _writer[1]
    # The path changed (tests point EVENT_DB_PATH at a fresh temp DB per case).
    # Only one is ever live, so drop the old handle rather than accumulating.
    _close_writer_locked()
    _ensure_schema(path)
    conn = sqlite3.connect(path, timeout=5, check_same_thread=False)
    conn.execute("PRAGMA synchronous=NORMAL")
    _writer = (key, conn)
    return conn


def _close_writer_locked() -> None:
    """Drop the shared write connection. Caller must hold _writer_lock."""
    global _writer
    if _writer is None:
        return
    try:
        _writer[1].close()
    except Exception:
        pass
    _writer = None


def close_connections() -> None:
    """Close the shared write connection (app shutdown, and between tests)."""
    with _writer_lock:
        _close_writer_locked()


def _write(sql: str, params: tuple, what: str) -> None:
    """Execute one insert on the shared connection. Never raises."""
    try:
        with _writer_lock:
            try:
                conn = _writer_connection(_db_path())
                conn.execute(sql, params)
                conn.commit()
            except Exception:
                # A broken handle would poison every later event, so drop it and
                # let the next call reopen. Still swallowed below: this module's
                # contract is that analytics never break an operation.
                _close_writer_locked()
                raise
    except Exception:
        logger.warning("Failed to record %s", what, exc_info=True)


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
    request_bytes: Optional[int] = None,
) -> None:
    """Record one operation event. Never raises."""
    ctx_country, ctx_session = get_request_context()
    if country is None:
        country = ctx_country
    if session_id is None:
        session_id = ctx_session
    if request_bytes is None:
        request_bytes = get_request_bytes()
    _write(
        "INSERT INTO operation_events"
        " (timestamp, operation, use_ai, success, duration_ms, error, country,"
        "  session_id, request_bytes)"
        " VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            operation,
            1 if use_ai else 0,
            1 if success else 0,
            int(duration_ms),
            sanitize_error(error),
            country,
            session_id,
            request_bytes,
        ),
        f"operation event for {operation}",
    )


async def alog_event(operation: str, **kwargs) -> None:
    """log_event() from async code, off the event loop.

    asyncio.to_thread copies the current context, so the contextvar-backed
    request context still resolves inside the worker.
    """
    await asyncio.to_thread(lambda: log_event(operation, **kwargs))


async def timed(operation: str, awaitable: Awaitable, use_ai: bool = False):
    """Await an operation call, logging its outcome and duration.

    The logging is awaited on a worker thread: timed() wraps essentially every
    endpoint in main.py, so a synchronous SQLite write here landed on the event
    loop and stalled every *other* in-flight request too.
    """
    started = time.perf_counter()
    try:
        result = await awaitable
    except Exception as exc:
        await alog_event(
            operation,
            success=False,
            duration_ms=(time.perf_counter() - started) * 1000,
            use_ai=use_ai,
            error=exc,
        )
        raise
    await alog_event(
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
    request_bytes: Optional[int] = None,
    **kwargs,
):
    """Synchronous counterpart of timed() for sync call sites and worker threads.

    Raw worker threads don't inherit contextvars, so callers there pass
    country/session_id/request_bytes explicitly — same reason for all three.
    """
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
            request_bytes=request_bytes,
        )
        raise
    log_event(
        operation,
        success=True,
        duration_ms=(time.perf_counter() - started) * 1000,
        use_ai=use_ai,
        country=country,
        session_id=session_id,
        request_bytes=request_bytes,
    )
    return result


# Sentinels stored in place of a host. `(direct)` is a page view with no
# referrer at all: someone who typed the URL, opened a bookmark, or arrived from
# an app or client that strips it.
REFERRER_DIRECT = "(direct)"
# ...and a page view referred by our own site, i.e. internal navigation. Kept
# distinct from (direct) so it can be excluded from acquisition numbers instead
# of quietly inflating them.
REFERRER_INTERNAL = "(internal)"
_HOST_MAX = 100
_HOST_RE = re.compile(r"^[A-Za-z0-9.\-]+$")


def referrer_host(referrer: Optional[str], self_host: Optional[str] = None) -> str:
    """Reduce a referring URL to a bare lowercase host, or a sentinel.

    Only the host survives — never the path or query string. A referring URL's
    query is the part that can carry a search term or an identifier, and none of
    it is needed to answer the question this metric exists for ("which sites
    send us traffic"). Anything unparseable is treated as no referrer rather
    than stored as-is, so the column can only ever hold a hostname or a
    sentinel.
    """
    if not referrer:
        return REFERRER_DIRECT
    try:
        host = urlsplit(str(referrer).strip()).hostname or ""
    except ValueError:
        return REFERRER_DIRECT
    host = host.lower().lstrip(".")[:_HOST_MAX]
    if not host or not _HOST_RE.match(host):
        return REFERRER_DIRECT
    if self_host:
        self_host = self_host.lower()
        if host == self_host or host.endswith("." + self_host):
            return REFERRER_INTERNAL
    # 'www.' carries no information and would split google.com into two rows.
    return host[4:] if host.startswith("www.") else host


def log_funnel_event(
    event: str,
    *,
    label: Optional[str] = None,
    country: Optional[str] = None,
    session_id: Optional[str] = None,
    referrer: Optional[str] = None,
) -> bool:
    """Record one navigation/funnel event. Never raises.

    `referrer` must already be reduced to a host by referrer_host() — this
    function stores it verbatim.

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
    if referrer is not None:
        referrer = str(referrer)[:_HOST_MAX]
    _write(
        "INSERT INTO funnel_events"
        " (timestamp, event, label, country, session_id, referrer)"
        " VALUES (?, ?, ?, ?, ?, ?)",
        (
            datetime.now(timezone.utc).isoformat(timespec="milliseconds"),
            event,
            label,
            country,
            session_id,
            referrer,
        ),
        f"funnel event {event}",
    )
    return True


# Note: there is deliberately no aggregation/reporting code below this point.
# query_stats(), query_funnel(), and normalize_since() — the read side that
# powers /admin/stats — live in the private deployment's admin_stats.py, which
# calls get_connection() above. This module only ever writes to the DB, so the
# public repo carries no admin surface at all.
