"""Tests for Google AdSense integration, Consent Mode v2, and ads.txt across all public pages."""
import pytest
from fastapi.testclient import TestClient

import main
from main import app
from scripts import seo_content, blog_content

EXPECTED_PUB_ID = "ca-pub-2992458363092462"
EXPECTED_SCRIPT_SRC = f"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={EXPECTED_PUB_ID}"
EXPECTED_ADS_TXT = "google.com, pub-2992458363092462, DIRECT, f08c47fec0942fa0"


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def enable_adsense(monkeypatch):
    monkeypatch.setattr(main, "ADSENSE_CLIENT", EXPECTED_PUB_ID)
    monkeypatch.setattr(main, "ADSENSE_HEAD_HTML", main._build_adsense_head())
    monkeypatch.setattr(main, "ADSENSE_SLOT_HTML", main._build_adsense_slot())
    monkeypatch.setattr(main, "CONSENT_BANNER_HTML", main._build_consent_banner())
    main._render_page.cache_clear()
    main._render_tool_page.cache_clear()
    yield
    main._render_page.cache_clear()
    main._render_tool_page.cache_clear()


def _assert_adsense_present(html: str, context: str = ""):
    assert EXPECTED_SCRIPT_SRC in html, f"AdSense script tag missing in {context}"
    assert 'crossorigin="anonymous"' in html, f"crossorigin attribute missing in {context}"
    assert "adsbygoogle.js" in html, f"adsbygoogle.js missing in {context}"
    assert "<head>" in html and "</head>" in html, f"<head> tags missing in {context}"
    head_content = html.split("</head>")[0]
    assert EXPECTED_SCRIPT_SRC in head_content, f"AdSense script not inside <head> in {context}"
    # Consent Mode v2 check
    assert "gtag('consent','default'" in head_content or "gtag('consent', 'default'" in head_content, f"Consent mode missing in <head> in {context}"


def test_index_page_contains_adsense(client, enable_adsense):
    res = client.get("/")
    assert res.status_code == 200
    _assert_adsense_present(res.text, "index page (/)")
    assert 'id="ff-consent"' in res.text, "Consent banner missing on index page"


@pytest.mark.parametrize("slug", ["about", "contact", "faq", "privacy", "terms"])
def test_static_content_pages_contain_adsense(client, enable_adsense, slug):
    res = client.get(f"/{slug}")
    assert res.status_code == 200
    _assert_adsense_present(res.text, f"content page (/{slug})")
    assert 'id="ff-consent"' in res.text, f"Consent banner missing on content page (/{slug})"


@pytest.mark.parametrize("slug", list(seo_content.TOOL_PAGES.keys()))
def test_tool_landing_pages_contain_adsense(client, enable_adsense, slug):
    res = client.get(f"/{slug}")
    assert res.status_code == 200
    _assert_adsense_present(res.text, f"tool page (/{slug})")
    assert 'id="ff-consent"' in res.text, f"Consent banner missing on tool page (/{slug})"


def test_blog_index_and_guides_contain_adsense(client, enable_adsense):
    res = client.get("/blog")
    assert res.status_code == 200
    _assert_adsense_present(res.text, "blog index (/blog)")

    for slug in blog_content.guide_slugs():
        g_res = client.get(f"/blog/{slug}")
        assert g_res.status_code == 200
        _assert_adsense_present(g_res.text, f"blog guide (/blog/{slug})")


def test_ads_txt_endpoint(client, monkeypatch):
    monkeypatch.setenv("ADSENSE_ADS_TXT", EXPECTED_ADS_TXT)
    res = client.get("/ads.txt")
    assert res.status_code == 200
    assert res.headers["content-type"].startswith("text/plain")
    assert res.text.strip() == EXPECTED_ADS_TXT


def test_adsense_clean_when_disabled(client, monkeypatch):
    monkeypatch.setattr(main, "ADSENSE_CLIENT", "")
    monkeypatch.setattr(main, "ADSENSE_HEAD_HTML", main._build_adsense_head())
    monkeypatch.setattr(main, "ADSENSE_SLOT_HTML", main._build_adsense_slot())
    monkeypatch.setattr(main, "CONSENT_BANNER_HTML", main._build_consent_banner())
    main._render_page.cache_clear()
    main._render_tool_page.cache_clear()

    for path in ["/", "/about", "/contact", "/faq", "/privacy", "/terms", "/merge-pdf", "/blog"]:
        res = client.get(path)
        assert res.status_code == 200
        assert "{{ADSENSE" not in res.text
        assert "{{CONSENT_BANNER}}" not in res.text
        assert "adsbygoogle" not in res.text
        assert "ff-consent" not in res.text
