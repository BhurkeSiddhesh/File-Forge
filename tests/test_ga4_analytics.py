"""Tests for optional Google Analytics 4 instrumentation."""
from fastapi.testclient import TestClient
import pytest

import main
from main import app
from scripts import blog_content, seo_content

GA_ID = "G-TEST12345"
GA_SRC = f"https://www.googletagmanager.com/gtag/js?id={GA_ID}"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def ga_enabled(monkeypatch):
    monkeypatch.setattr(main, "GA_MEASUREMENT_ID", GA_ID)
    monkeypatch.setattr(main, "GA_ANALYTICS_HTML", main._build_ga_analytics())
    main._render_page.cache_clear()
    main._render_tool_page.cache_clear()
    yield
    monkeypatch.setattr(main, "GA_MEASUREMENT_ID", "")
    monkeypatch.setattr(main, "GA_ANALYTICS_HTML", "")
    main._render_page.cache_clear()
    main._render_tool_page.cache_clear()


def _assert_ga_present(html: str, context: str = ""):
    assert GA_SRC in html, f"GA4 source missing in {context}"
    assert "window.ffAnalytics" in html, f"ffAnalytics bridge missing in {context}"
    assert "send_page_view:false" in html, f"manual pageview config missing in {context}"
    assert "transport_type:'beacon'" in html, f"beacon transport missing in {context}"
    assert "{{GA_ANALYTICS}}" not in html, f"GA token was not substituted in {context}"
    head_content = html.split("</head>")[0]
    assert GA_SRC in head_content, f"GA4 script not inside <head> in {context}"


def test_ga_is_absent_until_configured(client):
    main.GA_MEASUREMENT_ID = ""
    main.GA_ANALYTICS_HTML = ""
    main._render_page.cache_clear()

    res = client.get("/")

    assert res.status_code == 200
    assert "googletagmanager.com/gtag/js" not in res.text
    assert "{{GA_ANALYTICS}}" not in res.text


def test_index_page_contains_ga4_with_manual_spa_pageviews(client, ga_enabled):
    res = client.get("/")

    assert res.status_code == 200
    _assert_ga_present(res.text, "index page (/)")
    assert "window.FF_GA_MANUAL_PAGEVIEW=true" in res.text


@pytest.mark.parametrize("slug", ["about", "contact", "faq", "privacy", "terms"])
def test_static_content_pages_contain_ga4(client, ga_enabled, slug):
    res = client.get(f"/{slug}")

    assert res.status_code == 200
    _assert_ga_present(res.text, f"content page (/{slug})")
    assert "window.FF_GA_MANUAL_PAGEVIEW=true" not in res.text


@pytest.mark.parametrize("slug", list(seo_content.TOOL_PAGES.keys()))
def test_tool_landing_pages_contain_ga4(client, ga_enabled, slug):
    res = client.get(f"/{slug}")

    assert res.status_code == 200
    _assert_ga_present(res.text, f"tool page (/{slug})")


def test_blog_index_guides_and_404_contain_ga4(client, ga_enabled):
    res = client.get("/blog")
    assert res.status_code == 200
    _assert_ga_present(res.text, "blog index (/blog)")

    for slug in blog_content.guide_slugs():
        g_res = client.get(f"/blog/{slug}")
        assert g_res.status_code == 200
        _assert_ga_present(g_res.text, f"blog guide (/blog/{slug})")

    missing = client.get("/non-existent-page-12345")
    assert missing.status_code == 404
    _assert_ga_present(missing.text, "404 page")


def test_frontend_mirrors_safe_intent_events_to_ga4():
    script = (main.BASE_DIR / "static" / "script.js").read_text(encoding="utf-8")

    assert "function ffTrackGoogleAnalytics(event, label)" in script
    assert "window.ffAnalytics.event(event, label || '')" in script
    assert "function ffTrackPageView(path, title)" in script
    assert "ffTrackPageView('/app/' + encodeURIComponent(tool), document.title)" in script
    assert "file_processed" in script
    assert "file_downloaded" in script
    assert "filename" not in script.partition("function ffTrackGoogleAnalytics")[2].partition("function ffTrackPageView")[0]
