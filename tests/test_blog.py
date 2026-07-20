"""Tests for the /blog guides section (long-tail SEO content).

Pins the contract: index + every guide render as valid, fully-substituted HTML
with correct canonical/JSON-LD, guides funnel to a real tool, unknown guides
404, and the guides appear in sitemap.xml + llms.txt.
"""
import json
import re

from fastapi.testclient import TestClient

from main import app
from scripts import blog_content
from scripts.seo_content import TOOL_PAGES

_JSONLD = re.compile(r'<script type="application/ld\+json">(.*?)</script>', re.S)


def test_blog_index_renders():
    r = TestClient(app).get("/blog")
    assert r.status_code == 200
    assert "File Forge Guides" in r.text
    assert "{{" not in r.text  # all template tokens substituted
    # index links to every guide
    for slug in blog_content.guide_slugs():
        assert f"/blog/{slug}" in r.text


def test_every_guide_renders_with_valid_seo():
    client = TestClient(app)
    for slug in blog_content.guide_slugs():
        r = client.get(f"/blog/{slug}")
        assert r.status_code == 200, slug
        body = r.text
        assert "{{" not in body, f"unsubstituted token in /blog/{slug}"
        # self-referential canonical
        assert f'<link rel="canonical" href="' in body
        assert f"/blog/{slug}" in body
        # indexable
        assert 'name="robots" content="index, follow' in body
        # all JSON-LD blocks parse; Article + BreadcrumbList + FAQPage present
        types = set()
        for m in _JSONLD.findall(body):
            types.add(json.loads(m).get("@type"))
        assert {"Article", "BreadcrumbList", "FAQPage"} <= types, (slug, types)


def test_every_guide_points_at_a_real_tool():
    for slug, g in blog_content.GUIDES.items():
        assert g["primary_tool"] in TOOL_PAGES, (slug, g["primary_tool"])
        for r in g["related"]:
            assert r in TOOL_PAGES, (slug, r)


def test_unknown_guide_is_404():
    assert TestClient(app).get("/blog/does-not-exist").status_code == 404


def test_guides_in_sitemap_and_llms():
    client = TestClient(app)
    sitemap = client.get("/sitemap.xml").text
    llms = client.get("/llms.txt").text
    assert "/blog</loc>" in sitemap
    for slug in blog_content.guide_slugs():
        assert f"/blog/{slug}</loc>" in sitemap
        assert f"/blog/{slug}" in llms
