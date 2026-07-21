from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi import UploadFile, File, Form, HTTPException, Request
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, PlainTextResponse, Response
import asyncio
import shutil
import os
import uuid
import html
import json
import logging
from functools import lru_cache
from pathlib import Path

# --- Logging Setup ---
LOG_LEVEL = os.environ.get("LOG_LEVEL", "INFO").upper()
logger = logging.getLogger("file_forge")
logger.setLevel(LOG_LEVEL)

# Ensure logs are emitted if no parent handlers exist (e.g., when running directly)
if not logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
    logger.addHandler(handler)

from fastapi.concurrency import run_in_threadpool
from scripts.pdf_utils import (
    remove_pdf_password,
    pdf_to_docx,
    pdf_to_word_ai,
    extract_pdf_pages,
    compress_pdf,
    merge_pdfs,
    add_watermark,
    pdf_to_images_zip,
    sign_pdf,
    rotate_pdf,
    protect_pdf,
    images_to_pdf,
    word_to_pdf,
    word_to_pptx,
    pdf_to_excel,
    pdf_to_pptx,
    extract_text_from_pdf,
    organize_pdf,
    add_page_numbers,
    repair_pdf,
    create_pdf_from_text,
    create_blank_pdf,
    annotate_pdf,
    edit_pdf_metadata,
    get_pdf_metadata,
)
from scripts.image_utils import (
    heic_to_jpeg,
    rotate_image,
    compress_image,
    convert_image_format,
    watermark_image,
)
from scripts.excel_utils import (
    excel_to_pdf,
    csv_to_xlsx,
    xlsx_to_csv,
    merge_excel_files,
)
from scripts.ppt_utils import (
    ppt_to_pdf,
    ppt_to_images_zip,
    merge_pptx,
)
from scripts import seo_content
from scripts import blog_content
from scripts import event_log

PROD = os.environ.get("ENV") == "production"
app = FastAPI(
    title="Forge Files API",
    docs_url=None if PROD else "/docs",
    redoc_url=None if PROD else "/redoc",
    openapi_url=None if PROD else "/openapi.json",
)

# --- CORS ---
# The web frontend is served same-origin (no CORS needed there), but the
# Capacitor mobile app loads its assets from capacitor://localhost (iOS) and
# http://localhost (Android) and calls this API cross-origin. Allow those
# origins plus any explicitly configured web origins (comma-separated in
# CORS_EXTRA_ORIGINS, e.g. the production site domain).
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402

_CORS_ORIGINS = [
    "capacitor://localhost",
    "http://localhost",
    "https://localhost",
]
_CORS_ORIGINS += [
    o.strip()
    for o in os.environ.get("CORS_EXTRA_ORIGINS", "").split(",")
    if o.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# --- Configuration ---
BASE_URL = os.environ.get("BASE_URL", "https://www.forgefiles.org").rstrip("/")
# Stable sitemap <lastmod>. Tool/content pages are static, so reporting today's
# date on every request is inaccurate and teaches crawlers to distrust the field
# (wasting crawl budget). Bump CONTENT_LAST_MODIFIED (or set the env var on a
# real content change) so the sitemap reflects the true last edit, not "now".
CONTENT_LAST_MODIFIED = os.environ.get("CONTENT_LAST_MODIFIED", "2026-07-20").strip()
MAX_UPLOAD_MB = int(os.environ.get("MAX_UPLOAD_MB", "50"))
DISABLE_AI = os.environ.get("DISABLE_AI", "0") == "1"
FILE_TTL_SECONDS = int(os.environ.get("FILE_TTL_SECONDS", "3600"))

# --- Google AdSense (optional, fully env-gated) ---
# When ADSENSE_CLIENT is unset, every ad placeholder renders empty — zero markup,
# zero performance impact. Ads load asynchronously and lazily (IntersectionObserver),
# inside fixed reserved-height containers so they never cause layout shift (CLS).
ADSENSE_CLIENT = os.environ.get("ADSENSE_CLIENT", "").strip()  # e.g. ca-pub-1234567890123456
ADSENSE_SLOT = os.environ.get("ADSENSE_SLOT", "").strip()      # numeric data-ad-slot (optional)


def _build_adsense_head() -> str:
    if not ADSENSE_CLIENT:
        return ""
    # Consent-gated (Google Consent Mode v2): storage/personalization default to
    # 'denied' before the AdSense script runs, and the lazy ad-fill only happens
    # once the visitor accepts via the consent banner (or on a prior 'granted'
    # choice persisted in localStorage). The banner calls window.__ffConsentInit()
    # on accept to fill any ads already in view. Declining leaves ads unfilled.
    #
    # Ad-free gate (build-prompt task 4.5): before filling, we make a best-effort
    # call to the backend-controlled GET /api/me and skip ads entirely (hiding the
    # reserved .ad-slot boxes) when features.ad_free is true. The public app only
    # ever reads features.ad_free — never entitlement internals. The session token
    # comes from window.__ffSession (populated by the auth layer once login is
    # wired); with no token — the current free-launch default, payments off — the
    # gate resolves to "show ads", so behaviour is identical to before.
    return (
        '<link rel="preconnect" href="https://pagead2.googlesyndication.com" crossorigin>\n'
        '    <script>window.dataLayer=window.dataLayer||[];function gtag(){dataLayer.push(arguments);}'
        "gtag('consent','default',{ad_storage:'denied',ad_user_data:'denied',"
        "ad_personalization:'denied',analytics_storage:'denied',wait_for_update:500});</script>\n"
        '    <script async src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client='
        + ADSENSE_CLIENT + '" crossorigin="anonymous"></script>\n'
        '    <script>\n'
        "    (function(){var K='ff_consent';function granted(){return localStorage.getItem(K)==='granted';}"
        'function fill(el){try{(adsbygoogle=window.adsbygoogle||[]).push({});'
        "el.setAttribute('data-lazy-filled','1');}catch(e){}}"
        "function hideSlots(){var s=document.querySelectorAll('.ad-slot');"
        'for(var i=0;i<s.length;i++){s[i].style.display=\'none\';}}'
        'function adFree(cb){var t=(window.__ffSession&&window.__ffSession.access_token);'
        'if(!t){cb(false);return;}'
        "fetch('/api/me',{headers:{Authorization:'Bearer '+t}})"
        '.then(function(r){return r.ok?r.json():null;})'
        '.then(function(d){cb(!!(d&&d.features&&d.features.ad_free));})'
        '.catch(function(){cb(false);});}'
        "function runFill(){if(!granted())return;"
        "var ads=document.querySelectorAll('ins.adsbygoogle:not([data-lazy-filled])');"
        "if(!('IntersectionObserver' in window)){ads.forEach(fill);return;}"
        'var io=new IntersectionObserver(function(es){es.forEach(function(e){'
        "if(e.isIntersecting){io.unobserve(e.target);fill(e.target);}});},{rootMargin:'250px'});"
        'ads.forEach(function(a){io.observe(a);});}'
        'function init(){adFree(function(af){if(af){hideSlots();return;}runFill();});}'
        'window.__ffConsentInit=init;'
        "if(document.readyState!=='loading'){init();}else{document.addEventListener('DOMContentLoaded',init);}})();\n"
        '    </script>'
    )


def _build_consent_banner() -> str:
    """Cookie-consent banner shown until the visitor accepts/declines.

    Only emitted when ADSENSE_CLIENT is set — with no ads there are no ad cookies
    to consent to, so the banner (like the ad markup) is zero-markup when unset.
    This is the consent mechanism AdSense requires before serving personalized
    ads (build-prompt task 4.6). Accepting flips Consent Mode to 'granted' and
    triggers the lazy ad-fill; declining persists the choice and leaves ads off.
    """
    if not ADSENSE_CLIENT:
        return ""
    return (
        '<div id="ff-consent" role="dialog" aria-live="polite" aria-label="Cookie consent" hidden'
        ' style="position:fixed;left:0;right:0;bottom:0;z-index:9999;display:flex;flex-wrap:wrap;'
        'gap:12px;align-items:center;justify-content:center;padding:14px 18px;'
        'background:#181b22;color:#e8eaed;border-top:1px solid #262b35;'
        'font:14px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif">'
        '<span style="max-width:640px">We use cookies to serve ads that keep Forge Files free. '
        'See our <a href="/privacy" style="color:#4f8cff">Privacy Policy</a>.</span>'
        '<span style="display:flex;gap:8px">'
        '<button id="ff-consent-decline" type="button" style="cursor:pointer;border:1px solid #262b35;'
        'border-radius:8px;padding:8px 16px;background:transparent;color:#e8eaed;font:inherit">Decline</button>'
        '<button id="ff-consent-accept" type="button" style="cursor:pointer;border:0;'
        'border-radius:8px;padding:8px 16px;background:#4f8cff;color:#fff;font:inherit;font-weight:600">Accept</button>'
        '</span></div>\n'
        '<script>(function(){'
        "var K='ff_consent',b=document.getElementById('ff-consent');if(!b)return;"
        'if(!localStorage.getItem(K)){b.hidden=false;}'
        'function choose(v){localStorage.setItem(K,v);b.hidden=true;'
        "if(v==='granted'){try{gtag('consent','update',{ad_storage:'granted',ad_user_data:'granted',"
        "ad_personalization:'granted',analytics_storage:'granted'});}catch(e){}"
        'if(window.__ffConsentInit)window.__ffConsentInit();}}'
        "document.getElementById('ff-consent-accept').onclick=function(){choose('granted');};"
        "document.getElementById('ff-consent-decline').onclick=function(){choose('denied');};"
        '})();</script>'
    )


def _build_adsense_slot() -> str:
    if not ADSENSE_CLIENT:
        return ""
    slot_attr = f' data-ad-slot="{ADSENSE_SLOT}"' if ADSENSE_SLOT else ""
    return (
        '<div class="ad-slot" role="complementary" aria-label="Advertisement">'
        '<ins class="adsbygoogle" style="display:block"'
        f' data-ad-client="{ADSENSE_CLIENT}"{slot_attr}'
        ' data-ad-format="auto" data-full-width-responsive="true"></ins>'
        '</div>'
    )


ADSENSE_HEAD_HTML = _build_adsense_head()
ADSENSE_SLOT_HTML = _build_adsense_slot()
CONSENT_BANNER_HTML = _build_consent_banner()

# --- Search engine site verification (optional, fully env-gated) ---
# Paste the token (not the whole meta tag) from Google Search Console / Bing
# Webmaster Tools. When unset, no verification markup is emitted.
GOOGLE_SITE_VERIFICATION = os.environ.get("GOOGLE_SITE_VERIFICATION", "").strip()
BING_SITE_VERIFICATION = os.environ.get("BING_SITE_VERIFICATION", "").strip()


def _build_site_verification() -> str:
    tags = []
    if GOOGLE_SITE_VERIFICATION:
        tags.append(
            f'<meta name="google-site-verification" content="{html.escape(GOOGLE_SITE_VERIFICATION, quote=True)}">'
        )
    if BING_SITE_VERIFICATION:
        tags.append(
            f'<meta name="msvalidate.01" content="{html.escape(BING_SITE_VERIFICATION, quote=True)}">'
        )
    return "\n    ".join(tags)


SITE_VERIFICATION_HTML = _build_site_verification()

# --- Cloudflare Web Analytics (optional, fully env-gated) ---
# Paste the site token from the Cloudflare dashboard (Web Analytics → your site →
# "JS snippet" — it's the value of data-cf-beacon's "token"). When unset, no
# beacon is emitted, so there is zero third-party JS and zero performance cost.
#
# Cloudflare Web Analytics is cookieless and privacy-first: it records page views
# and Core Web Vitals only (no custom events). That already gives the page-to-page
# navigation funnel (home → tool page → …). The *"did they actually process a
# file"* funnel steps are emitted client-side via window.zaraz.track() in
# script.js — those show up in Cloudflare when Zaraz is enabled on the zone, and
# are silent no-ops otherwise, so nothing here depends on Zaraz being present.
CLOUDFLARE_ANALYTICS_TOKEN = os.environ.get("CLOUDFLARE_ANALYTICS_TOKEN", "").strip()


def _build_cf_analytics() -> str:
    if not CLOUDFLARE_ANALYTICS_TOKEN:
        return ""
    token = json.dumps(CLOUDFLARE_ANALYTICS_TOKEN)  # JSON-safe, quoted
    return (
        '<script defer src="https://static.cloudflareinsights.com/beacon.min.js" '
        f"data-cf-beacon='{{\"token\": {token}}}'></script>"
    )


CF_ANALYTICS_HTML = _build_cf_analytics()

AI_DISABLED_MESSAGE = (
    "AI Layout Recovery is disabled on this server (it needs more memory than the "
    "free hosting tier provides). Uncheck 'Use AI Layout Recovery' to use the standard converter."
)

@app.on_event("startup")
async def startup_event():
    """Optionally warm up AI models, and start the stale-file sweeper."""
    asyncio.create_task(cleanup_stale_files_loop())
    if os.environ.get("WARMUP_AI") != "1" or DISABLE_AI:
        return
    logger.info("Initializing AI Models... This may take a while on first run.")
    try:
        from fastapi.concurrency import run_in_threadpool
        from scripts.ocr_engine import get_ocr_engine
        engine = await run_in_threadpool(get_ocr_engine)
        logger.info("OCR backend ready: %s", engine.name if engine else "none")
    except Exception as e:
        logger.warning("AI Model initialization failed: %s", e)


# Ensure directories exist
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# --- Stale-file sweeper (privacy guarantee) ---
from scripts.security_utils import secure_filename

def _delete_stale_files(directory: Path, ttl: int) -> None:
    now = __import__("time").time()
    for f in directory.iterdir():
        try:
            if f.is_file() and (now - f.stat().st_mtime) > ttl:
                f.unlink(missing_ok=True)
        except Exception:
            pass

async def cleanup_stale_files_loop():
    while True:
        from fastapi.concurrency import run_in_threadpool as _rtp
        for d in (UPLOAD_DIR, OUTPUT_DIR):
            await _rtp(_delete_stale_files, d, FILE_TTL_SECONDS)
        await asyncio.sleep(900)

ALLOWED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg", ".webp", ".heic",
                      ".xlsx", ".docx", ".pptx", ".csv"}

def save_upload(file: UploadFile) -> Path:
    """Save an uploaded file using a pure UUID name and validate its extension."""
    import pathlib
    exts = pathlib.PurePath(file.filename or "").suffixes
    ext = "".join(exts).lower() if exts else ""
    # Simplify extension if it's too long or weird, but usually we just want the last suffix.
    # Actually, ''.join(exts) can be '.tar.gz', so check if it ends with one of the allowed extensions,
    # or just use the last suffix.
    final_ext = exts[-1].lower() if exts else ""
    if final_ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=415, detail=f"Unsupported file type: {final_ext}")
        
    dest = (UPLOAD_DIR / f"{uuid.uuid4().hex}{final_ext}").resolve()
    
    # Ensure it stays in the sandbox
    try:
        dest.relative_to(UPLOAD_DIR.resolve())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid path")

    max_bytes = MAX_UPLOAD_MB * 1024 * 1024
    written = 0
    too_large = False
    with dest.open("wb") as out:
        while chunk := file.file.read(1024 * 1024):
            written += len(chunk)
            if written > max_bytes:
                too_large = True
                break
            out.write(chunk)
    if too_large:
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail=f"File exceeds {MAX_UPLOAD_MB} MB limit.")
    return dest

# --- Rate Limiting (Issue #47) ---
import time
import threading
from collections import defaultdict, deque


class SlidingWindowRateLimiter:
    """Thread-safe in-memory sliding-window rate limiter keyed by client."""

    def __init__(self, window_seconds: float = 60.0):
        self.window = window_seconds
        self._hits = defaultdict(deque)
        self._lock = threading.Lock()

    def check(self, key: str, limit: int):
        """Record a hit for `key`. Returns (allowed, retry_after_seconds)."""
        now = time.monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - self.window:
                hits.popleft()
            if len(hits) >= limit:
                retry_after = int(self.window - (now - hits[0])) + 1
                return False, retry_after
            hits.append(now)
            return True, 0

    def reset(self):
        with self._lock:
            self._hits.clear()


# Endpoints that are CPU/memory intensive get a stricter limit
RATE_LIMIT_HEAVY_PATHS = {
    "/api/pdf/convert-to-word",
    "/api/pdf/convert-to-word-stream",
    "/api/workflow/execute",
    "/api/pdf/to-excel",
    "/api/pdf/to-pptx",
    "/api/word/to-pptx",
}

app.state.rate_limiter = SlidingWindowRateLimiter()
app.state.rate_limit_enabled = os.environ.get("RATE_LIMIT_ENABLED", "1").lower() not in ("0", "false", "no")
app.state.rate_limit_heavy = int(os.environ.get("RATE_LIMIT_HEAVY", "5"))    # req/min per IP
app.state.rate_limit_light = int(os.environ.get("RATE_LIMIT_LIGHT", "20"))   # req/min per IP
# Funnel beacons (/api/track) get their own generous bucket so page-view pings
# never eat into a visitor's file-operation budget (the "light" tier).
app.state.rate_limit_track = int(os.environ.get("RATE_LIMIT_TRACK", "120"))  # req/min per IP


@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    state = request.app.state
    if not getattr(state, "rate_limit_enabled", False) or not request.url.path.startswith("/api/"):
        return await call_next(request)

    client_ip = request.client.host if request.client else "unknown"
    if request.url.path == "/api/track":
        tier, limit = "track", getattr(state, "rate_limit_track", 120)
    elif request.url.path in RATE_LIMIT_HEAVY_PATHS:
        tier, limit = "heavy", state.rate_limit_heavy
    else:
        tier, limit = "light", state.rate_limit_light

    allowed, retry_after = state.rate_limiter.check(f"{client_ip}:{tier}", limit)
    if not allowed:
        logger.warning("Rate limit exceeded for %s on %s", client_ip, request.url.path)
        return JSONResponse(
            status_code=429,
            content={"detail": "Too many requests. Please slow down."},
            headers={"Retry-After": str(retry_after)},
        )
    return await call_next(request)


# --- Anonymous operation-event context (server-side analytics, no tracking script) ---
SESSION_COOKIE_NAME = "ff_sid"
SESSION_COOKIE_MAX_AGE = 365 * 24 * 3600


@app.middleware("http")
async def event_context_middleware(request: Request, call_next):
    """Expose CF-IPCountry and an anonymous session id to scripts/event_log.

    Only /api/ requests get the context and cookie: every operation lives under
    /api/, and page views are deliberately not tracked. The session id is a
    random UUID in a first-party cookie tied to nothing — no PII, and IP
    addresses are never stored anywhere.
    """
    if not request.url.path.startswith("/api/"):
        return await call_next(request)
    country = request.headers.get("cf-ipcountry")
    session_id = request.cookies.get(SESSION_COOKIE_NAME)
    is_new_session = session_id is None
    if is_new_session:
        session_id = str(uuid.uuid4())
    token = event_log.set_request_context(country, session_id)
    try:
        response = await call_next(request)
    finally:
        event_log.reset_request_context(token)
    if is_new_session:
        response.set_cookie(
            SESSION_COOKIE_NAME,
            session_id,
            max_age=SESSION_COOKIE_MAX_AGE,
            httponly=True,
            samesite="lax",
        )
    return response

# --- Input Validation Helpers (Issue #45) ---

def validate_range(name: str, value, min_value=None, max_value=None):
    """Validate that a numeric parameter falls within an allowed range.

    None values are allowed (treated as "not provided"); callers enforce
    required parameters separately. Raises 422 on invalid input.
    """
    if value is None:
        return
    if min_value is not None and value < min_value:
        raise HTTPException(
            status_code=422,
            detail=f"{name} must be >= {min_value} (got {value})",
        )
    if max_value is not None and value > max_value:
        raise HTTPException(
            status_code=422,
            detail=f"{name} must be <= {max_value} (got {value})",
        )


def validate_quality(quality: int):
    """JPEG quality must be in [1, 95] (Pillow recommends <= 95)."""
    validate_range("quality", quality, 1, 95)


def _substitute(html_text: str) -> str:
    """Replace server-side template tokens shared by every page."""
    return (
        html_text
        .replace("{{BASE_URL}}", BASE_URL)
        .replace("{{ADSENSE_HEAD}}", ADSENSE_HEAD_HTML)
        .replace("{{ADSENSE_SLOT}}", ADSENSE_SLOT_HTML)
        .replace("{{CONSENT_BANNER}}", CONSENT_BANNER_HTML)
        .replace("{{SITE_VERIFICATION}}", SITE_VERIFICATION_HTML)
        .replace("{{CF_ANALYTICS}}", CF_ANALYTICS_HTML)
    )


@lru_cache(maxsize=64)
def _render_page(relative_path: str) -> str:
    raw = (BASE_DIR / "static" / relative_path).read_text(encoding="utf-8")
    return _substitute(raw)


@lru_cache(maxsize=64)
def _render_tool_page(slug: str) -> str:
    """Server-render a tool landing page (full HTML, no JS needed for crawlers)."""
    return _substitute(seo_content.render_tool_page(slug))

@app.get("/")
async def read_index():
    return HTMLResponse(_render_page("index.html"))

@app.post("/api/pdf/remove-password")
async def api_remove_password(
    file: UploadFile = File(...),
    password: str = Form(...)
):
    temp_path = save_upload(file)
    try:
        output_path = event_log.timed_call(
            "pdf_unlock", remove_pdf_password, str(temp_path), password, str(OUTPUT_DIR)
        )
        return {"status": "success", "message": "Password removed", "filename": Path(output_path).name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass

@app.post("/api/pdf/convert-to-word")
async def api_convert_to_word(
    file: UploadFile = File(...),
    use_ai: bool = Form(False),
    password: str = Form(None)
):
    # Sanitize filename and add UUID prefix
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    logger.debug("Converting: %s, use_ai=%s, password=%s", safe_filename, use_ai, '***' if password else 'None')
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        logger.debug("File saved to: %s", temp_path)
        
        if use_ai:
            # @jules: This can be very slow for large PDFs. 
            # We should probably implement a progress bar or background task with polling.
            output_path = event_log.timed_call(
                "pdf_to_word_ai", pdf_to_word_ai, str(temp_path), str(OUTPUT_DIR), password,
                use_ai=True,
            )
            message = "Converted to Word with AI Layout Recovery"
        else:
            output_path = await event_log.timed(
                "pdf_to_word_standard",
                run_in_threadpool(pdf_to_docx, str(temp_path), str(OUTPUT_DIR), password),
            )
            message = "Converted to Word (Standard)"

        logger.info("Conversion successful: %s", output_path)
        return {"status": "success", "message": message, "filename": Path(output_path).name}
    except Exception as e:
        logger.exception("Conversion failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))

    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass  # Windows file locking - will be cleaned up later

@app.post("/api/pdf/convert-to-word-stream")
async def api_convert_to_word_stream(
    file: UploadFile = File(...),
    use_ai: bool = Form(False),
    password: str = Form(None)
):
    """Convert PDF to Word with real-time SSE progress events (Issue #46).

    Streams events: {"event": "start"}, {"event": "progress", "page": n,
    "total": t}, then {"event": "complete", "filename": ...} or
    {"event": "error", "detail": ...}.
    """
    import json
    import queue as queue_mod
    from fastapi.responses import StreamingResponse

    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Captured here because the worker runs on a raw thread, where the
    # middleware's contextvars don't propagate.
    ctx_country, ctx_session = event_log.get_request_context()
    op_name = "pdf_to_word_ai" if use_ai else "pdf_to_word_standard"

    async def event_stream():
        events = queue_mod.Queue()

        def progress_cb(page_done, total_pages):
            events.put({"event": "progress", "page": page_done, "total": total_pages})

        def worker():
            try:
                if use_ai:
                    output_path = event_log.timed_call(
                        op_name, pdf_to_word_ai,
                        str(temp_path), str(OUTPUT_DIR), password, progress_callback=progress_cb,
                        use_ai=True, country=ctx_country, session_id=ctx_session,
                    )
                    message = "Converted to Word with AI Layout Recovery"
                else:
                    output_path = event_log.timed_call(
                        op_name, pdf_to_docx, str(temp_path), str(OUTPUT_DIR), password,
                        country=ctx_country, session_id=ctx_session,
                    )
                    message = "Converted to Word (Standard)"
                events.put({
                    "event": "complete",
                    "message": message,
                    "filename": Path(output_path).name,
                })
            except Exception as e:
                logger.exception("Streaming conversion failed for %s", safe_filename)
                events.put({"event": "error", "detail": event_log.scrub_paths(str(e))})
            finally:
                events.put(None)  # sentinel: stream finished

        yield f"data: {json.dumps({'event': 'start', 'filename': safe_filename})}\n\n"
        thread = threading.Thread(target=worker, daemon=True)
        thread.start()
        try:
            while True:
                item = await run_in_threadpool(events.get)
                if item is None:
                    break
                yield f"data: {json.dumps(item)}\n\n"
        finally:
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except PermissionError:
                    pass

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@app.post("/api/pdf/extract-pages")
async def api_extract_pages(
    file: UploadFile = File(...),
    pages: str = Form(...),
    password: str = Form(None),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    logger.debug("Extracting pages: %s, pages='%s', password=%s", safe_filename, pages, '***' if password else 'None')
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await event_log.timed(
            "page_extract",
            run_in_threadpool(extract_pdf_pages, str(temp_path), str(OUTPUT_DIR), pages, password),
        )
        return {"status": "success", "message": "Pages extracted", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Page extraction failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/compress")
async def api_compress_pdf(
    file: UploadFile = File(...),
    level: str = Form('medium'),
    password: str = Form(None)
):
    """Compress PDF by optimizing structure and resampling large images."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    logger.debug("Compressing: %s, level=%s, password=%s", safe_filename, level, '***' if password else 'None')
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await event_log.timed(
            "pdf_compress",
            run_in_threadpool(compress_pdf, str(temp_path), str(OUTPUT_DIR), level, password or None),
        )
        return {
            "status": "success",
            "message": "PDF compressed successfully",
            "filename": Path(result['output_path']).name,
            "original_size": result['original_size'],
            "compressed_size": result['compressed_size'],
            "reduction_pct": result['reduction_pct'],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("PDF compression failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/merge")
async def api_merge_pdfs(
    files: List[UploadFile] = File(...),
    passwords: Optional[str] = Form(None),
):
    """Merge multiple PDFs into one. `passwords` is an optional comma-separated list aligned with files."""
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two PDF files to merge.")

    temp_paths: List[Path] = []
    try:
        for f in files:
            safe_filename = Path(f.filename.replace("\\", "/")).name
            unique_filename = f"{uuid.uuid4()}_{safe_filename}"
            temp_path = UPLOAD_DIR / unique_filename
            with temp_path.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(temp_path)

        pwd_list = None
        if passwords:
            pwd_list = [p if p else None for p in passwords.split(",")]

        output_path = await event_log.timed(
            "pdf_merge",
            run_in_threadpool(merge_pdfs, [str(p) for p in temp_paths], str(OUTPUT_DIR), pwd_list),
        )
        return {"status": "success", "message": "PDFs merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("PDF merge failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        for p in temp_paths:
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


@app.post("/api/pdf/watermark")
async def api_add_watermark(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("diagonal"),
    opacity: float = Form(0.3),
    password: str = Form(None),
):
    """Stamp a text watermark on every page."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await event_log.timed(
            "pdf_watermark",
            run_in_threadpool(
                add_watermark, str(temp_path), str(OUTPUT_DIR), text, position, opacity, password or None
            ),
        )
        return {"status": "success", "message": "Watermark added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Watermark failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/rotate")
async def api_rotate_pdf(
    file: UploadFile = File(...),
    angle: int = Form(...),
    pages: str = Form(None),
    password: str = Form(None),
):
    """Rotate PDF pages by specified angle (90, 180, 270 degrees)."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await event_log.timed(
            "pdf_rotate",
            run_in_threadpool(
                rotate_pdf, str(temp_path), str(OUTPUT_DIR), angle, pages or None, password or None
            ),
        )
        return {"status": "success", "message": f"PDF rotated by {angle}°", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("PDF rotation failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/to-images")
async def api_pdf_to_images(
    file: UploadFile = File(...),
    dpi: int = Form(150),
    fmt: str = Form("jpg"),
    password: str = Form(None),
):
    """Render every page to an image and return a zip."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await event_log.timed(
            "pdf_to_images",
            run_in_threadpool(
                pdf_to_images_zip, str(temp_path), str(OUTPUT_DIR), dpi, fmt, password or None
            ),
        )
        return {
            "status": "success",
            "message": f"Rendered {result['page_count']} page(s) to images",
            "filename": Path(result["output_path"]).name,
            "page_count": result["page_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("PDF to images failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/sign")
async def api_sign_pdf(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
    page: int = Form(1),
    x: float = Form(0.65),
    y: float = Form(0.85),
    width: float = Form(0.2),
    password: str = Form(None),
):
    """Stamp a signature image onto the chosen page."""
    sig_ct = (signature.content_type or "").lower()
    if sig_ct not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="Signature must be a PNG or JPEG image.")

    safe_pdf = Path(file.filename.replace("\\", "/")).name
    safe_sig = Path(signature.filename.replace("\\", "/")).name
    pdf_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_pdf}"
    sig_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_sig}"
    try:
        with pdf_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        with sig_path.open("wb") as buffer:
            shutil.copyfileobj(signature.file, buffer)

        output_path = await event_log.timed(
            "pdf_sign",
            run_in_threadpool(
                sign_pdf, str(pdf_path), str(sig_path), str(OUTPUT_DIR), page, x, y, width, password or None
            ),
        )
        return {"status": "success", "message": "Signature added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Sign PDF failed for %s", safe_pdf)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        for p in (pdf_path, sig_path):
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


@app.post("/api/image/heic-to-jpeg")
async def api_heic_to_jpeg(
    file: UploadFile = File(...),
    quality: int = Form(95),
):
    """Convert HEIC/HEIF image to JPEG format."""
    validate_quality(quality)
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    logger.debug("Converting HEIC: %s, quality=%d", safe_filename, quality)
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = event_log.timed_call(
            "heic_to_jpeg", heic_to_jpeg, str(temp_path), str(OUTPUT_DIR), quality
        )
        return {"status": "success", "message": "Converted to JPEG", "filename": Path(output_path).name}
    except Exception as e:
        logger.exception("HEIC conversion failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass  # Windows file locking - will be cleaned up later


@app.post("/api/image/resize")
async def api_resize_image(
    file: UploadFile = File(...),
    mode: str = Form(...),
    width: int = Form(None),
    height: int = Form(None),
    percentage: int = Form(None),
    target_size_kb: int = Form(None),
):
    """Resize image based on parameters."""
    if mode not in ("dimensions", "percentage", "target_size"):
        raise HTTPException(status_code=422, detail="mode must be one of: dimensions, percentage, target_size")
    validate_range("width", width, 1)
    validate_range("height", height, 1)
    validate_range("percentage", percentage, 1, 500)
    validate_range("target_size_kb", target_size_kb, 1)
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    logger.debug("Resizing image: %s, mode=%s", safe_filename, mode)
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from scripts.image_utils import resize_image
        output_path = event_log.timed_call(
            "resize",
            resize_image,
            str(temp_path),
            str(OUTPUT_DIR),
            mode,
            width=width,
            height=height,
            percentage=percentage,
            target_size_kb=target_size_kb
        )
        return {"status": "success", "message": "Image Resized", "filename": Path(output_path).name}
    except Exception as e:
        logger.exception("Image resize failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/image/crop")
async def api_crop_image(
    file: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...),
):
    """Crop image based on coordinates."""
    validate_range("x", x, 0)
    validate_range("y", y, 0)
    validate_range("width", width, 1)
    validate_range("height", height, 1)
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    logger.debug("Cropping image: %s, x=%d, y=%d, w=%d, h=%d", safe_filename, x, y, width, height)
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from scripts.image_utils import crop_image
        output_path = event_log.timed_call(
            "crop",
            crop_image,
            str(temp_path),
            str(OUTPUT_DIR),
            x=x, y=y, width=width, height=height
        )
        return {"status": "success", "message": "Image Cropped", "filename": Path(output_path).name}
    except Exception as e:
        logger.exception("Image crop failed for %s", safe_filename)
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/image/rotate")
async def api_rotate_image(
    file: UploadFile = File(...),
    angle: float = Form(90),
    quality: int = Form(95),
):
    validate_quality(quality)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "image_rotate",
            run_in_threadpool(rotate_image, str(temp_path), str(OUTPUT_DIR), angle, quality),
        )
        return {"status": "success", "message": f"Rotated by {angle}°", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/compress")
async def api_compress_image(
    file: UploadFile = File(...),
    quality: int = Form(70),
):
    validate_quality(quality)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await event_log.timed(
            "image_compress",
            run_in_threadpool(compress_image, str(temp_path), str(OUTPUT_DIR), quality),
        )
        return {
            "status": "success",
            "message": "Image compressed",
            "filename": Path(result["output_path"]).name,
            "original_size": result["original_size"],
            "compressed_size": result["compressed_size"],
            "reduction_pct": result["reduction_pct"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/convert")
async def api_convert_image(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    quality: int = Form(90),
):
    validate_quality(quality)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "image_convert",
            run_in_threadpool(convert_image_format, str(temp_path), str(OUTPUT_DIR), target_format, quality),
        )
        return {"status": "success", "message": f"Converted to {target_format.upper()}", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/watermark")
async def api_watermark_image(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.4),
    color: str = Form("white"),
):
    validate_range("opacity", opacity, 0.0, 1.0)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "image_watermark",
            run_in_threadpool(watermark_image, str(temp_path), str(OUTPUT_DIR), text, position, opacity, color),
        )
        return {"status": "success", "message": "Watermark added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


# --- Excel Routes ---

@app.post("/api/excel/to-pdf")
async def api_excel_to_pdf(
    file: UploadFile = File(...),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "excel_to_pdf", run_in_threadpool(excel_to_pdf, str(temp_path), str(OUTPUT_DIR))
        )
        return {"status": "success", "message": "Excel converted to PDF", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/csv-to-xlsx")
async def api_csv_to_xlsx(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "csv_to_xlsx", run_in_threadpool(csv_to_xlsx, str(temp_path), str(OUTPUT_DIR), delimiter)
        )
        return {"status": "success", "message": "CSV converted to XLSX", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/xlsx-to-csv")
async def api_xlsx_to_csv(
    file: UploadFile = File(...),
    sheet: str = Form(None),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "xlsx_to_csv", run_in_threadpool(xlsx_to_csv, str(temp_path), str(OUTPUT_DIR), sheet or None)
        )
        return {"status": "success", "message": "XLSX converted to CSV", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/merge")
async def api_merge_excel(
    files: List[UploadFile] = File(...),
):
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two Excel files to merge.")
    temp_paths: List[Path] = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(tp)
        output_path = await event_log.timed(
            "excel_merge",
            run_in_threadpool(merge_excel_files, [str(p) for p in temp_paths], str(OUTPUT_DIR)),
        )
        return {"status": "success", "message": "Excel files merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        for p in temp_paths:
            if p.exists():
                try: os.remove(p)
                except PermissionError: pass


# --- PPT Routes ---

@app.post("/api/ppt/to-pdf")
async def api_ppt_to_pdf(
    file: UploadFile = File(...),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "ppt_to_pdf", run_in_threadpool(ppt_to_pdf, str(temp_path), str(OUTPUT_DIR))
        )
        return {"status": "success", "message": "PPT converted to PDF (best-effort layout)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/ppt/to-images")
async def api_ppt_to_images(
    file: UploadFile = File(...),
    fmt: str = Form("png"),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await event_log.timed(
            "ppt_to_images", run_in_threadpool(ppt_to_images_zip, str(temp_path), str(OUTPUT_DIR), fmt)
        )
        return {
            "status": "success",
            "message": f"Rendered {result['slide_count']} slide(s)",
            "filename": Path(result["output_path"]).name,
            "slide_count": result["slide_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/ppt/merge")
async def api_merge_pptx(
    files: List[UploadFile] = File(...),
):
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two PPTX files to merge.")
    temp_paths: List[Path] = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(tp)
        output_path = await event_log.timed(
            "ppt_merge",
            run_in_threadpool(merge_pptx, [str(p) for p in temp_paths], str(OUTPUT_DIR)),
        )
        return {"status": "success", "message": "PPTX files merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        logger.exception("Endpoint failed")
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        for p in temp_paths:
            if p.exists():
                try: os.remove(p)
                except PermissionError: pass


@app.post("/api/workflow/execute")
async def execute_workflow(
    file: UploadFile = File(...),
    steps: str = Form(...),
):
    """Execute a multi-step workflow on a file with SSE progress streaming."""
    import json
    from fastapi.responses import StreamingResponse

    # Sanitize filename and add UUID prefix to prevent path traversal and concurrent collisions
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    
    logger.info("Workflow started: %s, steps=%s", safe_filename, steps)
    
    # Parse steps JSON
    try:
        step_list = json.loads(steps)
        if not step_list:
            raise ValueError("No steps provided")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid steps JSON")
    
    # Save initial file
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)

    # Captured here because generate_progress runs while the response streams,
    # outside the middleware's request context.
    wf_country, wf_session = event_log.get_request_context()

    async def generate_progress():
        """Generator for SSE progress events."""
        current_file = temp_path

        def log_step(step_type, ok, started, config, err=None):
            # config may be a non-dict if the client sent a malformed step; the
            # operation itself raises on that and we still want to log the
            # failure cleanly rather than crash the SSE stream.
            use_ai = bool(config.get('use_ai', False)) if isinstance(config, dict) else False
            event_log.log_event(
                step_type,
                success=ok,
                duration_ms=(time.perf_counter() - started) * 1000,
                use_ai=use_ai,
                error=err,
                country=wf_country,
                session_id=wf_session,
            )

        step_started = None  # non-None only while a step's processing call runs

        try:
            # Process each step
            for i, step in enumerate(step_list):
                step_type = step.get('type')
                config = step.get('config', {})
                step_label = step.get('label', step_type)

                # Send "processing" event for this step
                yield f"data: {json.dumps({'event': 'step_start', 'step': i, 'total': len(step_list), 'label': step_label})}\n\n"

                logger.debug("Step %d: %s", i+1, step_type)

                # Artificial delay to ensure UI updates are visible
                import asyncio
                await asyncio.sleep(1.0)

                # Timing starts after the UI delay so the artificial second
                # never inflates the logged step duration.
                step_started = time.perf_counter()

                if step_type == 'remove_password':
                    password = config.get('password', '')
                    if not password:
                        yield f"data: {json.dumps({'event': 'error', 'detail': 'Password required for unlock step'})}\n\n"
                        return
                    output_path = await run_in_threadpool(remove_pdf_password, str(current_file), password, str(OUTPUT_DIR))
                    current_file = Path(output_path)
                    
                elif step_type == 'pdf_to_word':
                    use_ai = config.get('use_ai', False)
                    password = config.get('password')
                    if use_ai:
                        output_path = await run_in_threadpool(pdf_to_word_ai, str(current_file), str(OUTPUT_DIR), password)
                    else:
                        output_path = await run_in_threadpool(pdf_to_docx, str(current_file), str(OUTPUT_DIR), password)
                    current_file = Path(output_path)
                    
                elif step_type == 'heic_to_jpeg':
                    quality = config.get('quality', 95)
                    output_path = await run_in_threadpool(heic_to_jpeg, str(current_file), str(OUTPUT_DIR), quality)
                    current_file = Path(output_path)
                    
                elif step_type == 'resize_image':
                    from scripts.image_utils import resize_image
                    mode = config.get('mode', 'percentage')
                    percentage = config.get('percentage', 50)
                    output_path = await run_in_threadpool(
                        resize_image,
                        str(current_file), 
                        str(OUTPUT_DIR), 
                        mode,
                        percentage=percentage
                    )
                    current_file = Path(output_path)
                    
                elif step_type == 'crop_image':
                    from scripts.image_utils import crop_image
                    x = config.get('x', 0)
                    y = config.get('y', 0)
                    width = config.get('width', 100)
                    height = config.get('height', 100)
                    output_path = await run_in_threadpool(
                        crop_image,
                        str(current_file), 
                        str(OUTPUT_DIR), 
                        x=x, y=y, width=width, height=height
                    )
                    current_file = Path(output_path)

                elif step_type == 'compress_pdf':
                    level = config.get('level', 'medium')
                    password = config.get('password') or None
                    result = await run_in_threadpool(compress_pdf, str(current_file), str(OUTPUT_DIR), level, password)
                    current_file = Path(result['output_path'])

                elif step_type == 'rotate_image':
                    angle = config.get('angle', 90)
                    output_path = await run_in_threadpool(rotate_image, str(current_file), str(OUTPUT_DIR), angle)
                    current_file = Path(output_path)

                elif step_type == 'compress_image':
                    quality = config.get('quality', 70)
                    result = await run_in_threadpool(compress_image, str(current_file), str(OUTPUT_DIR), quality)
                    current_file = Path(result['output_path'])

                elif step_type == 'convert_image':
                    target_format = config.get('target_format', 'jpg')
                    quality = config.get('quality', 90)
                    output_path = await run_in_threadpool(
                        convert_image_format, str(current_file), str(OUTPUT_DIR), target_format, quality
                    )
                    current_file = Path(output_path)

                elif step_type == 'watermark_image':
                    text = config.get('text', 'WATERMARK')
                    position = config.get('position', 'bottom-right')
                    opacity = config.get('opacity', 0.4)
                    color = config.get('color', 'white')
                    output_path = await run_in_threadpool(
                        watermark_image, str(current_file), str(OUTPUT_DIR), text, position, opacity, color
                    )
                    current_file = Path(output_path)

                elif step_type == 'excel_to_pdf':
                    output_path = await run_in_threadpool(excel_to_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(output_path)

                elif step_type == 'csv_to_xlsx':
                    delimiter = config.get('delimiter', ',')
                    output_path = await run_in_threadpool(csv_to_xlsx, str(current_file), str(OUTPUT_DIR), delimiter)
                    current_file = Path(output_path)

                elif step_type == 'xlsx_to_csv':
                    sheet = config.get('sheet') or None
                    output_path = await run_in_threadpool(xlsx_to_csv, str(current_file), str(OUTPUT_DIR), sheet)
                    current_file = Path(output_path)

                elif step_type == 'ppt_to_pdf':
                    output_path = await run_in_threadpool(ppt_to_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(output_path)

                elif step_type == 'ppt_to_images':
                    fmt = config.get('fmt', 'png')
                    result = await run_in_threadpool(ppt_to_images_zip, str(current_file), str(OUTPUT_DIR), fmt)
                    current_file = Path(result['output_path'])

                elif step_type == 'rotate_pdf':
                    angle = int(config.get('angle', 90))
                    pages = config.get('pages') or None
                    password = config.get('password') or None
                    output_path = await run_in_threadpool(rotate_pdf, str(current_file), str(OUTPUT_DIR), angle, pages, password)
                    current_file = Path(output_path)

                elif step_type == 'protect_pdf':
                    user_pw = config.get('user_password', '')
                    if not user_pw:
                        yield f"data: {json.dumps({'event': 'error', 'detail': 'user_password required for protect_pdf step'})}\n\n"
                        return
                    output_path = await run_in_threadpool(
                        protect_pdf, str(current_file), str(OUTPUT_DIR),
                        user_pw, config.get('owner_password'), True, False, False, config.get('password')
                    )
                    current_file = Path(output_path)

                elif step_type == 'word_to_pdf':
                    output_path = await run_in_threadpool(word_to_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(output_path)

                elif step_type == 'word_to_pptx':
                    dpi = int(config.get('dpi', 150))
                    output_path = await run_in_threadpool(word_to_pptx, str(current_file), str(OUTPUT_DIR), dpi)
                    current_file = Path(output_path)

                elif step_type == 'pdf_to_excel':
                    password = config.get('password') or None
                    result = await run_in_threadpool(pdf_to_excel, str(current_file), str(OUTPUT_DIR), password)
                    current_file = Path(result['output_path'])

                elif step_type == 'pdf_to_pptx':
                    dpi = int(config.get('dpi', 150))
                    password = config.get('password') or None
                    output_path = await run_in_threadpool(pdf_to_pptx, str(current_file), str(OUTPUT_DIR), dpi, password)
                    current_file = Path(output_path)

                elif step_type == 'extract_text':
                    preserve = config.get('preserve_layout', False)
                    password = config.get('password') or None
                    result = await run_in_threadpool(extract_text_from_pdf, str(current_file), str(OUTPUT_DIR), preserve, password)
                    current_file = Path(result['output_path'])

                elif step_type == 'organize_pdf':
                    page_order = config.get('page_order', [])
                    if not page_order:
                        yield f"data: {json.dumps({'event': 'error', 'detail': 'page_order required for organize_pdf step'})}\n\n"
                        return
                    password = config.get('password') or None
                    output_path = await run_in_threadpool(organize_pdf, str(current_file), str(OUTPUT_DIR), page_order, password)
                    current_file = Path(output_path)

                elif step_type == 'add_page_numbers':
                    output_path = await run_in_threadpool(
                        add_page_numbers, str(current_file), str(OUTPUT_DIR),
                        config.get('position', 'bottom-center'),
                        int(config.get('start_number', 1)),
                        int(config.get('font_size', 12)),
                        int(config.get('skip_first', 0)),
                        config.get('fmt', 'decimal'),
                        config.get('password') or None,
                    )
                    current_file = Path(output_path)

                elif step_type == 'repair_pdf':
                    result = await run_in_threadpool(repair_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(result['output_path'])

                elif step_type == 'annotate_pdf':
                    annotations = config.get('annotations', [])
                    password = config.get('password') or None
                    output_path = await run_in_threadpool(annotate_pdf, str(current_file), str(OUTPUT_DIR), annotations, password)
                    current_file = Path(output_path)

                elif step_type == 'edit_metadata':
                    output_path = await run_in_threadpool(
                        edit_pdf_metadata, str(current_file), str(OUTPUT_DIR),
                        config.get('title'), config.get('author'), config.get('subject'),
                        config.get('keywords'), config.get('creator'),
                        bool(config.get('clear_all', False)), config.get('password') or None,
                    )
                    current_file = Path(output_path)

                else:
                    yield f"data: {json.dumps({'event': 'error', 'detail': f'Unknown step type: {step_type}'})}\n\n"
                    return

                log_step(step_type, True, step_started, config)
                step_started = None

                # Rename this step's output off its "clean" branded name before the
                # next step runs. The next step's function derives its own output
                # name from the same original stem, so — for a same-extension step
                # (e.g. rotate_pdf after word_to_pdf) — it would otherwise compute
                # the exact path it's about to read from and fail (or, for tools
                # without pikepdf's overwrite guard, silently corrupt it).
                if i < len(step_list) - 1:
                    intermediate_path = OUTPUT_DIR / f"{uuid.uuid4()}_{current_file.name}"
                    current_file = current_file.replace(intermediate_path)

                # Send "completed" event for this step
                yield f"data: {json.dumps({'event': 'step_complete', 'step': i, 'total': len(step_list), 'label': step_label})}\n\n"

            # Send final success event
            logger.info("Workflow complete: %s", current_file)
            yield f"data: {json.dumps({'event': 'complete', 'message': f'Workflow completed ({len(step_list)} steps)', 'filename': current_file.name})}\n\n"

        except Exception as e:
            if step_started is not None:
                log_step(step_type, False, step_started, config, err=e)
            logger.exception("Workflow failed for %s", safe_filename)
            yield f"data: {json.dumps({'event': 'error', 'detail': event_log.scrub_paths(str(e))})}\n\n"
        
        finally:
            # Clean up temp file
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except PermissionError:
                    pass
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ─────────────────────────────────────────────────────────────
# Feature #53: Protect PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/protect")
async def api_protect_pdf(
    file: UploadFile = File(...),
    user_password: str = Form(...),
    owner_password: str = Form(None),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(False),
    allow_edit: bool = Form(False),
    password: str = Form(None),
):
    """Add password protection and permissions to a PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "pdf_protect",
            run_in_threadpool(
                protect_pdf, str(temp_path), str(OUTPUT_DIR),
                user_password, owner_password, allow_print, allow_copy, allow_edit, password or None
            ),
        )
        return {"status": "success", "message": "PDF protected with password", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #54: Image to PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/image/to-pdf")
async def api_images_to_pdf(
    files: List[UploadFile] = File(...),
    page_size: str = Form("A4"),
    fit_mode: str = Form("fit"),
    margin_pt: int = Form(36),
):
    """Convert one or more images into a single PDF."""
    validate_range("margin_pt", margin_pt, 0, 200)
    temp_paths = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buf:
                shutil.copyfileobj(f.file, buf)
            temp_paths.append(tp)

        output_path = await event_log.timed(
            "images_to_pdf",
            run_in_threadpool(
                images_to_pdf, [str(p) for p in temp_paths], str(OUTPUT_DIR), page_size, fit_mode, margin_pt
            ),
        )
        return {"status": "success", "message": f"Created PDF from {len(files)} image(s)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        for p in temp_paths:
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


# ─────────────────────────────────────────────────────────────
# Feature #55: Word to PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/word/to-pdf")
async def api_word_to_pdf(
    file: UploadFile = File(...),
):
    """Convert a Word document (DOCX/DOC) to PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "word_to_pdf", run_in_threadpool(word_to_pdf, str(temp_path), str(OUTPUT_DIR))
        )
        return {"status": "success", "message": "Word document converted to PDF", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/word/to-pptx")
async def api_word_to_pptx(
    file: UploadFile = File(...),
    dpi: int = Form(150),
):
    """Convert a Word document (DOCX/DOC) to a PowerPoint presentation."""
    validate_range("dpi", dpi, 30, 600)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "word_to_pptx", run_in_threadpool(word_to_pptx, str(temp_path), str(OUTPUT_DIR), dpi)
        )
        return {"status": "success", "message": "Word document converted to PowerPoint", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #56: PDF to Excel
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/to-excel")
async def api_pdf_to_excel(
    file: UploadFile = File(...),
    password: str = Form(None),
):
    """Extract tables from a PDF and convert to Excel."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await event_log.timed(
            "pdf_to_excel",
            run_in_threadpool(pdf_to_excel, str(temp_path), str(OUTPUT_DIR), password or None),
        )
        return {
            "status": "success",
            "message": f"Extracted {result['tables_found']} table(s) to Excel",
            "filename": Path(result["output_path"]).name,
            "tables_found": result["tables_found"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #57: PDF to PowerPoint
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/to-pptx")
async def api_pdf_to_pptx(
    file: UploadFile = File(...),
    dpi: int = Form(150),
    password: str = Form(None),
):
    """Convert PDF pages to a PowerPoint presentation."""
    validate_range("dpi", dpi, 30, 600)
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "pdf_to_pptx",
            run_in_threadpool(pdf_to_pptx, str(temp_path), str(OUTPUT_DIR), dpi, password or None),
        )
        return {"status": "success", "message": "PDF converted to PowerPoint", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #58: Extract Text from PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/extract-text")
async def api_extract_text(
    file: UploadFile = File(...),
    preserve_layout: bool = Form(False),
    password: str = Form(None),
):
    """Extract all text content from a PDF to a .txt file."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await event_log.timed(
            "pdf_extract_text",
            run_in_threadpool(
                extract_text_from_pdf, str(temp_path), str(OUTPUT_DIR), preserve_layout, password or None
            ),
        )
        return {
            "status": "success",
            "message": f"Text extracted from {result['page_count']} page(s)",
            "filename": Path(result["output_path"]).name,
            "page_count": result["page_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #59: Organize PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/organize")
async def api_organize_pdf(
    file: UploadFile = File(...),
    page_order: str = Form(...),
    password: str = Form(None),
):
    """Reorder, delete, or duplicate PDF pages. page_order is comma-separated 1-based page numbers."""
    import json as _json
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse page_order: accepts "1,3,2" or "[1,3,2]"
        raw = page_order.strip()
        if raw.startswith("["):
            order = _json.loads(raw)
        else:
            order = [int(x.strip()) for x in raw.split(",") if x.strip()]

        output_path = await event_log.timed(
            "pdf_organize",
            run_in_threadpool(organize_pdf, str(temp_path), str(OUTPUT_DIR), order, password or None),
        )
        return {"status": "success", "message": f"PDF organized ({len(order)} pages in output)", "filename": Path(output_path).name}
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #60: Add Page Numbers
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/add-page-numbers")
async def api_add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
    start_number: int = Form(1),
    font_size: int = Form(12),
    skip_first: int = Form(0),
    fmt: str = Form("decimal"),
    password: str = Form(None),
):
    """Insert page numbers onto each PDF page."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "pdf_add_page_numbers",
            run_in_threadpool(
                add_page_numbers, str(temp_path), str(OUTPUT_DIR),
                position, start_number, font_size, skip_first, fmt, password or None
            ),
        )
        return {"status": "success", "message": "Page numbers added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #61: Repair PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/repair")
async def api_repair_pdf(
    file: UploadFile = File(...),
):
    """Attempt to recover/repair a corrupted PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await event_log.timed(
            "pdf_repair", run_in_threadpool(repair_pdf, str(temp_path), str(OUTPUT_DIR))
        )
        return {
            "status": "success",
            "message": f"PDF repair status: {result['repair_status']}",
            "filename": Path(result["output_path"]).name,
            "repair_status": result["repair_status"],
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #62: Create PDF from Scratch
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/create-from-text")
async def api_create_pdf_from_text(
    content: str = Form(...),
    title: str = Form("Document"),
    font_size: int = Form(12),
    page_size: str = Form("A4"),
    margin_pt: int = Form(72),
):
    """Create a new PDF from plain text content."""
    try:
        output_path = await event_log.timed(
            "pdf_create_from_text",
            run_in_threadpool(
                create_pdf_from_text, str(OUTPUT_DIR), content, title, font_size, page_size, margin_pt
            ),
        )
        return {"status": "success", "message": "PDF created from text", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))


@app.post("/api/pdf/create-blank")
async def api_create_blank_pdf(
    num_pages: int = Form(1),
    page_size: str = Form("A4"),
):
    """Create a blank PDF with the given number of pages."""
    try:
        output_path = await event_log.timed(
            "pdf_create_blank", run_in_threadpool(create_blank_pdf, str(OUTPUT_DIR), num_pages, page_size)
        )
        return {"status": "success", "message": f"Created blank PDF with {num_pages} page(s)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))


# ─────────────────────────────────────────────────────────────
# Feature #63: Annotate / Edit PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/annotate")
async def api_annotate_pdf(
    file: UploadFile = File(...),
    annotations: str = Form(...),
    password: str = Form(None),
):
    """Add annotations (highlight/underline/strikeout/note/text/redact) to a PDF.
    annotations is a JSON array of annotation objects."""
    import json as _json
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        ann_list = _json.loads(annotations)
        if not isinstance(ann_list, list):
            raise ValueError("annotations must be a JSON array.")

        output_path = await event_log.timed(
            "pdf_annotate",
            run_in_threadpool(annotate_pdf, str(temp_path), str(OUTPUT_DIR), ann_list, password or None),
        )
        return {"status": "success", "message": f"Added {len(ann_list)} annotation(s)", "filename": Path(output_path).name}
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #64: PDF Metadata Editor
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/metadata")
async def api_edit_pdf_metadata(
    file: UploadFile = File(...),
    title: str = Form(None),
    author: str = Form(None),
    subject: str = Form(None),
    keywords: str = Form(None),
    creator: str = Form(None),
    clear_all: bool = Form(False),
    password: str = Form(None),
):
    """Edit PDF metadata (title, author, subject, keywords, creator)."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await event_log.timed(
            "pdf_edit_metadata",
            run_in_threadpool(
                edit_pdf_metadata, str(temp_path), str(OUTPUT_DIR),
                title, author, subject, keywords, creator, clear_all, password or None
            ),
        )
        return {"status": "success", "message": "PDF metadata updated", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/metadata/read")
async def api_read_pdf_metadata(
    file: UploadFile = File(...),
    password: str = Form(None),
):
    """Read metadata from a PDF without modifying it."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        metadata = await event_log.timed(
            "pdf_read_metadata", run_in_threadpool(get_pdf_metadata, str(temp_path), password or None)
        )
        return {"status": "success", "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=400, detail=event_log.scrub_paths(str(e)))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


def delete_file_after_download(path: Path) -> None:
    """
    Deletes the file at the given path.
    Designed to be used as a FastAPI BackgroundTask after a file has been served.
    
    Args:
        path: Path to the file to delete.
    """
    try:
        if path.exists():
            path.unlink()
            logger.debug("Deleted file after download: %s", path)
    except OSError:
        logger.exception("Failed to delete file %s", path)

@app.api_route("/api/download/{filename}", methods=["GET", "HEAD"])
async def download_file(filename: str, request: Request, background_tasks: BackgroundTasks):
    safe_filename = Path(filename.replace("\\", "/")).name
    file_path = OUTPUT_DIR / safe_filename
    if file_path.exists():
        if request.method == "GET":
            background_tasks.add_task(delete_file_after_download, file_path)
        return FileResponse(file_path, filename=safe_filename)
    raise HTTPException(status_code=404, detail="File not found")

# Note: there is deliberately no /admin/stats route in the public app. Only the
# write side of the event log (recording operations + funnel steps) lives here;
# the aggregation/reporting logic and the admin auth gate live in the private
# deployment's server.py, so the public repo never carries an admin surface.


# --- Anonymous funnel beacon (first-party, no third-party analytics) ---
@app.post("/api/track")
async def api_track(request: Request):
    """Record one anonymous navigation/funnel event (page_view, tool_open,
    file_processed, file_downloaded) into the local event log.

    This is the first-party replacement for a third-party analytics beacon: the
    browser POSTs a tiny JSON body ({event, label}) via navigator.sendBeacon, and
    the session id + coarse country come from the request-context middleware (this
    route is under /api/, so the anonymous ff_sid cookie and CF-IPCountry header
    are already applied). No file names, contents, IPs, or PII are ever stored.

    Always answers 204: a tracking beacon must never surface an error to the UI,
    and unknown event names are silently ignored inside log_funnel_event().
    """
    from functools import partial

    try:
        body = await request.json()
    except Exception:
        body = None
    if isinstance(body, dict):
        event = str(body.get("event") or "")[:40]
        label = body.get("label")
        label = label if isinstance(label, str) else None
        if event:
            await run_in_threadpool(partial(event_log.log_funnel_event, event, label=label))
    return Response(status_code=204)


# --- SEO Routes ---
# Content pages are static files in static/pages/. Tool pages are server-rendered
# from scripts/seo_content.py (full HTML — no JS required, so JS-less AI crawlers
# read the title/meta/body directly). Both kinds appear in sitemap.xml.
CONTENT_PAGES = ["about", "faq", "contact", "privacy", "terms"]
TOOL_PAGES = seo_content.TOOL_PAGES

# Back-compat: every indexable slug (tests and tooling expect this iterable).
SEO_PAGES = list(TOOL_PAGES.keys()) + CONTENT_PAGES

# AI retrieval/citation crawlers we explicitly welcome, so Forge Files tools are
# eligible to be cited in AI answers (ChatGPT, Perplexity, Gemini, Claude, ...).
AI_CRAWLERS = [
    "GPTBot", "OAI-SearchBot", "ChatGPT-User",
    "ClaudeBot", "Claude-Web", "anthropic-ai",
    "PerplexityBot", "Perplexity-User",
    "Google-Extended", "Applebot-Extended",
    "Amazonbot", "Bytespider", "Meta-ExternalAgent", "CCBot",
]


@app.get("/robots.txt", response_class=PlainTextResponse)
async def robots_txt():
    lines = ["# Forge Files: free, open-source file tools. All pages are public.", ""]
    for bot in AI_CRAWLERS:
        lines += [f"User-agent: {bot}", "Allow: /", "Disallow: /api/", ""]
    lines += ["User-agent: *", "Allow: /", "Disallow: /api/", ""]
    lines.append(f"Sitemap: {BASE_URL}/sitemap.xml")
    return PlainTextResponse("\n".join(lines) + "\n")


@app.get("/sitemap.xml")
async def sitemap_xml():
    lastmod = CONTENT_LAST_MODIFIED
    # (loc, changefreq, priority)
    entries = [(BASE_URL + "/", "daily", "1.0")]
    entries += [(f"{BASE_URL}/{slug}", "weekly", "0.8") for slug in TOOL_PAGES]
    entries += [(f"{BASE_URL}/blog", "weekly", "0.6")]
    entries += [(f"{BASE_URL}/blog/{slug}", "monthly", "0.6")
                for slug in blog_content.guide_slugs()]
    entries += [(f"{BASE_URL}/{slug}", "monthly", "0.5") for slug in CONTENT_PAGES]
    items = "\n".join(
        f"  <url><loc>{loc}</loc><lastmod>{lastmod}</lastmod>"
        f"<changefreq>{cf}</changefreq><priority>{pr}</priority></url>"
        for loc, cf, pr in entries
    )
    xml = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{items}\n</urlset>"
    )
    return Response(content=xml, media_type="application/xml")


# Human-readable category labels for the llms.txt grouping. Keyed by the "tool"
# field in seo_content.TOOL_PAGES; any category added there without an entry here
# falls back to a title-cased version of the key, so this can't 500 on new tools.
_LLMS_CATEGORIES = {
    "pdf": "PDF tools",
    "image": "Image tools",
    "excel": "Spreadsheet tools",
    "ppt": "Presentation tools",
    "word": "Document tools",
}


@app.get("/llms.txt", response_class=PlainTextResponse)
async def llms_txt():
    """Plain-text site index for LLM crawlers (the llms.txt convention).

    Generated from the same TOOL_PAGES/CONTENT_PAGES data as sitemap.xml, so the
    two can never drift: adding a tool to seo_content.py lists it here for free.
    Descriptions reuse each page's existing `meta` string rather than a second
    hand-written blurb, for the same reason.
    """
    lines = [
        "# Forge Files",
        "",
        "> Free, open-source online file tools: convert, compress, merge, split and "
        "edit PDFs, images and spreadsheets in the browser. No signup, no watermarks, "
        "no file-size paywall. Uploaded files are deleted from the server "
        "automatically after processing.",
        "",
        "Forge Files is free software (source: https://github.com/BhurkeSiddhesh/File-Forge) "
        "and can be self-hosted. Every tool below is a standalone page that works "
        "without JavaScript for reading purposes; no account is ever required.",
        "",
    ]

    by_category: dict = {}
    for slug, page in TOOL_PAGES.items():
        by_category.setdefault(page.get("tool") or "other", []).append((slug, page))

    for key in sorted(by_category, key=lambda k: -len(by_category[k])):
        lines.append(f"## {_LLMS_CATEGORIES.get(key, key.replace('-', ' ').title())}")
        lines.append("")
        for slug, page in sorted(by_category[key]):
            name = page.get("app") or slug
            lines.append(f"- [{name}]({BASE_URL}/{slug}): {page.get('meta', '')}")
        lines.append("")

    lines += ["## Guides", ""]
    for slug in blog_content.guide_slugs():
        g = blog_content.GUIDES[slug]
        lines.append(f"- [{g['h1']}]({BASE_URL}/blog/{slug}): {g['meta']}")
    lines.append("")

    lines += ["## About", ""]
    lines += [f"- [{slug.title()}]({BASE_URL}/{slug})" for slug in CONTENT_PAGES]
    lines.append("")

    return PlainTextResponse("\n".join(lines))


@app.get("/ads.txt", response_class=PlainTextResponse)
async def ads_txt():
    line = os.environ.get("ADSENSE_ADS_TXT", "").strip()
    if not line:
        raise HTTPException(status_code=404, detail="ads.txt not configured")
    return PlainTextResponse(line + "\n")


# Root-path icons. Every page already links /static/favicon.svg, but plenty of
# clients never parse the HTML and probe these fixed root paths directly —
# browsers falling back from an unsupported SVG icon, bookmark/feed readers, and
# iOS when a page is added to the home screen. Serving them here (rather than
# adding a <link> to all eight templates) covers the home page, all tool pages
# and all content pages at once. Must stay above the /{slug} catch-all below,
# which would otherwise swallow these as unknown slugs and 404.
@app.get("/favicon.ico", include_in_schema=False)
async def favicon_ico():
    return FileResponse(
        BASE_DIR / "static" / "favicon.ico",
        media_type="image/x-icon",
        headers={"Cache-Control": "public, max-age=604800"},
    )


@app.get("/apple-touch-icon.png", include_in_schema=False)
@app.get("/apple-touch-icon-precomposed.png", include_in_schema=False)
async def apple_touch_icon():
    return FileResponse(
        BASE_DIR / "static" / "apple-touch-icon.png",
        media_type="image/png",
        headers={"Cache-Control": "public, max-age=604800"},
    )


# --- Blog / guides (long-tail SEO content) ---------------------------------
# Registered ABOVE the /{slug} catch-all so "/blog" isn't swallowed as an unknown
# tool slug. "/blog/{slug}" is two segments so it never collides with /{slug}.
@app.get("/blog", response_class=HTMLResponse)
async def serve_blog_index():
    return HTMLResponse(_substitute(blog_content.render_blog_index()))


@app.get("/blog/{slug}", response_class=HTMLResponse)
async def serve_blog_guide(slug: str):
    if slug in blog_content.GUIDES:
        return HTMLResponse(_substitute(blog_content.render_guide(slug)))
    raise HTTPException(status_code=404, detail="Guide not found")


@app.get("/{slug}", response_class=HTMLResponse)
async def serve_seo_page(slug: str):
    if slug in TOOL_PAGES:
        return HTMLResponse(_render_tool_page(slug))
    if slug in CONTENT_PAGES:
        return HTMLResponse(_render_page(f"pages/{slug}.html"))
    raise HTTPException(status_code=404, detail="Page not found")


from starlette.exceptions import HTTPException as StarletteHTTPException


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Serve a branded, hard-404 HTML page for missing non-API routes (real status
    404 + real internal links, never a soft-404). API routes and every other
    status code keep the default JSON ``detail`` response."""
    if exc.status_code == 404 and not request.url.path.startswith("/api/"):
        return HTMLResponse(content=_substitute(seo_content.render_404_page()), status_code=404)
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.detail},
        headers=getattr(exc, "headers", None),
    )


if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
