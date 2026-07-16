"""The API-key auth system was removed — the app is fully public.

These tests pin down the new contract: no endpoint returns 401/403, and the
SEO routes (landing pages, robots.txt, sitemap.xml) are served correctly.
"""
from fastapi.testclient import TestClient
from main import app, SEO_PAGES, TOOL_PAGES, CONTENT_PAGES


def test_api_is_public_no_credentials_needed():
    """Processing endpoints must never ask for credentials (400 = validation, not 403)."""
    client = TestClient(app)
    response = client.post("/api/pdf/remove-password", data={})
    assert response.status_code not in (401, 403)


def test_download_is_public():
    """Download endpoint requires no key; missing file is a plain 404."""
    client = TestClient(app)
    response = client.get("/api/download/nonexistent.txt")
    assert response.status_code == 404


def test_download_head_does_not_delete_file(tmp_path, monkeypatch):
    """The frontend's HEAD pre-check must not consume (delete) the file."""
    import main as main_module
    monkeypatch.setattr(main_module, "OUTPUT_DIR", tmp_path)
    target = tmp_path / "result.txt"
    target.write_text("hello")

    client = TestClient(app)
    head = client.head("/api/download/result.txt")
    assert head.status_code == 200
    assert target.exists(), "HEAD request must not delete the file"

    get = client.get("/api/download/result.txt")
    assert get.status_code == 200
    assert not target.exists(), "GET download should delete the file afterwards"


def test_seo_pages_served():
    client = TestClient(app)
    for slug in SEO_PAGES:
        response = client.get(f"/{slug}")
        assert response.status_code == 200, f"/{slug} should be served"
        assert "{{BASE_URL}}" not in response.text, f"/{slug} must have BASE_URL substituted"
        assert "<link rel=\"canonical\"" in response.text


def test_unknown_page_returns_hard_404_html():
    """Missing web pages must return a real (hard) 404 status with a branded HTML
    body, not a soft-404 (200) or a bare JSON error — AI/search crawlers rely on it."""
    client = TestClient(app)
    r = client.get("/no-such-page")
    assert r.status_code == 404
    assert "text/html" in r.headers.get("content-type", "")
    assert "404" in r.text
    # the branded 404 links back into real tools so crawlers don't hit a dead end
    assert 'href="/merge-pdf"' in r.text


def test_api_404_stays_json():
    """API routes keep machine-readable JSON errors (not the HTML 404 page)."""
    client = TestClient(app)
    r = client.get("/api/download/definitely-not-real.txt")
    assert r.status_code == 404
    assert "application/json" in r.headers.get("content-type", "")


def test_tool_pages_render_with_full_schema():
    """Every tool landing page is fully server-rendered (no JS needed) with the
    title/meta/canonical and the four JSON-LD blocks crawlers use."""
    client = TestClient(app)
    sitemap = client.get("/sitemap.xml").text
    for slug in TOOL_PAGES:
        r = client.get(f"/{slug}")
        assert r.status_code == 200, f"/{slug} should be served"
        body = r.text
        assert "{{BASE_URL}}" not in body, f"/{slug} must have BASE_URL substituted"
        assert "<title>" in body and 'rel="canonical"' in body
        for schema in ("FAQPage", "SoftwareApplication", "HowTo", "BreadcrumbList"):
            assert schema in body, f"/{slug} missing {schema} schema"
        assert f"/{slug}" in sitemap, f"/{slug} missing from sitemap"


def test_tool_pages_have_substantial_security_copy():
    """Each tool page carries the server-rendered security/privacy section (~300+
    words of human-readable copy under the tool canvas) — strong on-page signal
    that JS-less AI crawlers can read directly from the raw HTML."""
    import re
    from scripts import seo_content

    for slug in TOOL_PAGES:
        body = seo_content.render_tool_page(slug)
        assert "keeps your" in body, f"/{slug} missing security-architecture section"
        # Word-count the visible copy only (strip tags) and require a healthy body.
        text = re.sub(r"<[^>]+>", " ", body)
        assert len(text.split()) >= 300, f"/{slug} has too little on-page copy"


def test_site_verification_meta_is_env_gated(monkeypatch):
    """Verification meta tags appear only when the env tokens are set, and the
    placeholder token never leaks into the response either way."""
    import main as main_module

    client = TestClient(app)
    for path in ("/", "/merge-pdf"):
        body = client.get(path).text
        assert "{{SITE_VERIFICATION}}" not in body
        assert "google-site-verification" not in body  # unset by default

    # Inject tokens at the module level (mirrors what the env vars produce) and
    # clear the page-render caches so the new <head> markup is emitted.
    verify_html = (
        '<meta name="google-site-verification" content="g-token-123">\n    '
        '<meta name="msvalidate.01" content="b-token-456">'
    )
    monkeypatch.setattr(main_module, "SITE_VERIFICATION_HTML", verify_html)
    main_module._render_page.cache_clear()
    main_module._render_tool_page.cache_clear()
    try:
        for path in ("/", "/merge-pdf"):
            body = client.get(path).text
            assert 'name="google-site-verification" content="g-token-123"' in body
            assert 'name="msvalidate.01" content="b-token-456"' in body
            assert "{{SITE_VERIFICATION}}" not in body
    finally:
        main_module._render_page.cache_clear()
        main_module._render_tool_page.cache_clear()


def test_robots_allows_ai_crawlers_and_sitemap():
    client = TestClient(app)
    robots = client.get("/robots.txt")
    assert robots.status_code == 200
    assert "Sitemap:" in robots.text
    for bot in ("GPTBot", "ClaudeBot", "PerplexityBot", "Google-Extended", "OAI-SearchBot"):
        assert bot in robots.text, f"{bot} should be named in robots.txt"

    sitemap = client.get("/sitemap.xml")
    assert sitemap.status_code == 200
    assert "<urlset" in sitemap.text
    assert "<priority>" in sitemap.text and "<lastmod>" in sitemap.text
    for slug in SEO_PAGES:
        assert f"/{slug}" in sitemap.text


def test_adsense_is_disabled_by_default():
    """With no ADSENSE_CLIENT configured, no ad markup or tokens leak into pages."""
    client = TestClient(app)
    for path in ("/", "/merge-pdf"):
        body = client.get(path).text
        assert "{{ADSENSE" not in body
        assert "{{CONSENT_BANNER}}" not in body  # token always substituted (to empty)
        assert "adsbygoogle" not in body
        assert "ff-consent" not in body  # no banner without ads to consent to


def test_consent_banner_and_ads_are_consent_gated_when_adsense_on():
    """When AdSense is configured, ads only fill after consent and a banner ships."""
    import main

    # Point the builders at a test publisher id without re-importing the app.
    saved = main.ADSENSE_CLIENT
    try:
        main.ADSENSE_CLIENT = "ca-pub-test"
        head = main._build_adsense_head()
        banner = main._build_consent_banner()
    finally:
        main.ADSENSE_CLIENT = saved

    # Consent Mode defaults to denied before the ad fill runs...
    assert "'default'" in head and "'denied'" in head
    # ...and the lazy fill is gated on a persisted 'granted' choice.
    assert "ff_consent" in head and "granted()" in head
    assert "window.__ffConsentInit" in head

    # The banner offers a real accept/decline choice and flips consent on accept.
    assert 'id="ff-consent"' in banner
    assert "ff-consent-accept" in banner and "ff-consent-decline" in banner
    assert "'update'" in banner and "'granted'" in banner


def test_ad_free_gate_hides_slots_from_backend_feature_when_adsense_on():
    """task 4.5: before filling ads the head script consults GET /api/me and hides
    the reserved .ad-slot boxes when features.ad_free is true — reading only the
    backend feature flag, never entitlement internals. With no session token the
    gate resolves to "show ads" (free-launch default), so behaviour is unchanged."""
    import main

    saved = main.ADSENSE_CLIENT
    try:
        main.ADSENSE_CLIENT = "ca-pub-test"
        head = main._build_adsense_head()
    finally:
        main.ADSENSE_CLIENT = saved

    # Reads the backend-controlled feature (not raw entitlement rows).
    assert "__ffSession" in head and "/api/me" in head
    assert "features.ad_free" in head and "hideSlots" in head
    # No session token → callback(false) → ads still show (free-launch default).
    assert "cb(false)" in head
    # The gate runs before the lazy fill: ad-free hides slots and returns early.
    assert "if(af){hideSlots();return;}runFill();" in head


def test_consent_banner_substitutes_into_served_page_when_adsense_on(monkeypatch):
    """End-to-end: with AdSense configured, a real served page carries the
    consent banner + Consent-Mode-denied default, and the {{CONSENT_BANNER}}
    token is fully substituted (never leaks raw)."""
    import main

    monkeypatch.setattr(main, "ADSENSE_CLIENT", "ca-pub-test")
    monkeypatch.setattr(main, "ADSENSE_HEAD_HTML", main._build_adsense_head())
    monkeypatch.setattr(main, "CONSENT_BANNER_HTML", main._build_consent_banner())
    main._render_page.cache_clear()  # drop the ad-free cached render
    try:
        body = TestClient(main.app).get("/").text
        assert 'id="ff-consent"' in body            # banner present in the page
        assert "consent','default'" in body          # Consent Mode default (denied)
        assert "granted()" in body                    # ad fill is consent-gated
        assert "{{CONSENT_BANNER}}" not in body       # token substituted, not leaked
    finally:
        main._render_page.cache_clear()  # don't poison the cache for other tests


def test_consent_builders_are_empty_without_adsense():
    """Belt-and-suspenders: no AdSense id => no head script and no banner."""
    import main

    saved = main.ADSENSE_CLIENT
    try:
        main.ADSENSE_CLIENT = ""
        assert main._build_adsense_head() == ""
        assert main._build_consent_banner() == ""
    finally:
        main.ADSENSE_CLIENT = saved


def test_homepage_has_seo_meta():
    client = TestClient(app)
    response = client.get("/")
    assert response.status_code == 200
    assert "meta name=\"description\"" in response.text
    assert "{{BASE_URL}}" not in response.text
    assert "application/ld+json" in response.text
