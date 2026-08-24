"""Tests for DataFast analytics tracking script installation in public app."""
import re
from fastapi.testclient import TestClient
import pytest

from main import app
from scripts import seo_content, blog_content

DATAFAST_SRC = "https://datafa.st/js/script.js"
DATAFAST_SITE_ID = "dfid_na6goRSY6Vnle9ErZzQbC"
DATAFAST_DOMAIN = "forgefiles.org"


def _assert_datafast_present(html: str, context: str = ""):
    assert DATAFAST_SRC in html, f"DataFast src missing in {context}"
    assert DATAFAST_SITE_ID in html, f"DataFast site ID missing in {context}"
    assert DATAFAST_DOMAIN in html, f"DataFast domain missing in {context}"
    assert 'data-website-id="dfid_na6goRSY6Vnle9ErZzQbC"' in html, f"data-website-id attr missing in {context}"
    assert 'data-domain="forgefiles.org"' in html, f"data-domain attr missing in {context}"
    assert "defer" in html, f"defer attribute missing in {context}"
    assert "<head>" in html and "</head>" in html, f"<head> tags missing in {context}"
    head_content = html.split("</head>")[0]
    assert DATAFAST_SRC in head_content, f"DataFast script not inside <head> in {context}"


@pytest.fixture
def client():
    return TestClient(app)


def test_index_page_contains_datafast(client):
    res = client.get("/")
    assert res.status_code == 200
    _assert_datafast_present(res.text, "index page (/)")


@pytest.mark.parametrize("slug", ["about", "contact", "faq", "privacy", "terms"])
def test_static_content_pages_contain_datafast(client, slug):
    res = client.get(f"/{slug}")
    assert res.status_code == 200
    _assert_datafast_present(res.text, f"content page (/{slug})")


@pytest.mark.parametrize("slug", list(seo_content.TOOL_PAGES.keys()))
def test_tool_landing_pages_contain_datafast(client, slug):
    res = client.get(f"/{slug}")
    assert res.status_code == 200
    _assert_datafast_present(res.text, f"tool page (/{slug})")


def test_blog_index_and_guides_contain_datafast(client):
    res = client.get("/blog")
    assert res.status_code == 200
    _assert_datafast_present(res.text, "blog index (/blog)")

    for slug in blog_content.guide_slugs():
        g_res = client.get(f"/blog/{slug}")
        assert g_res.status_code == 200
        _assert_datafast_present(g_res.text, f"blog guide (/blog/{slug})")


def test_404_page_contains_datafast(client):
    res = client.get("/non-existent-page-12345")
    assert res.status_code == 404
    _assert_datafast_present(res.text, "404 page")
