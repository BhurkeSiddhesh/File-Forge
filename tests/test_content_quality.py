"""Public claims must match the supplied evidence and navigable content."""
from __future__ import annotations

import hashlib
import json
import re
import xml.etree.ElementTree as ET
import zipfile
from html.parser import HTMLParser
from pathlib import Path

import fitz
import pytest
from fastapi.testclient import TestClient

from main import app
from scripts import blog_content, content_examples, seo_content


class Links(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.urls: set[str] = set()

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        data = dict(attrs)
        value = data.get("href" if tag == "a" else "src" if tag == "img" else "")
        if value and value.startswith("/"):
            self.urls.add(value)


def test_published_measurements_match_actual_files() -> None:
    data = content_examples.manifest()
    for name, item in data["files"].items():
        raw = (content_examples.ROOT / name).read_bytes()
        assert len(raw) == item["bytes"], name
        assert hashlib.sha256(raw).hexdigest() == item["sha256"], name
        if name.endswith(".pdf"):
            with fitz.open(stream=raw, filetype="pdf") as doc:
                assert len(doc) == item["pages"], name
    original = data["files"]["scan.pdf"]["bytes"]
    for level, result in data["compression"].items():
        actual = data["files"][f"scan-{level}.pdf"]["bytes"]
        assert result["original_size"] == original
        assert result["compressed_size"] == actual
        assert result["reduction_pct"] == pytest.approx(100 * (1 - actual / original), abs=.1)


def test_page_examples_preserve_the_promised_order() -> None:
    root = content_examples.ROOT
    with fitz.open(root / "report.pdf") as original, fitz.open(root / "extracted.pdf") as extracted:
        assert len(original) == 3 and len(extracted) == 2
        assert extracted[0].get_text() == original[0].get_text()
        assert extracted[1].get_text() == original[2].get_text()
    with fitz.open(root / "merged.pdf") as merged:
        assert len(merged) == 4
        assert "Workshop appendix" in merged[-1].get_text()
    with fitz.open(root / "scan.pdf") as scan:
        assert not scan[0].get_text().strip(), "the image-only example must not have a hidden text layer"


def test_word_example_contains_editable_text_and_table() -> None:
    with zipfile.ZipFile(content_examples.ROOT / "report.docx") as docx:
        root = ET.fromstring(docx.read("word/document.xml"))
    ns = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
    words = " ".join(n.text or "" for n in root.findall(".//w:t", ns))
    assert "Wood panels" in words and "Steel brackets" in words
    tables = root.findall(".//w:tbl", ns)
    assert tables, "the example must show a real editable table, not only a page image"


def test_aliases_redirect_and_are_not_separate_index_entries() -> None:
    client = TestClient(app)
    sitemap = client.get("/sitemap.xml").text
    for old, canonical in seo_content.CANONICAL_ALIASES.items():
        response = client.get(f"/{old}", follow_redirects=False)
        assert response.status_code == 308
        assert response.headers["location"] == f"/{canonical}"
        assert f"/{old}</loc>" not in sitemap
        assert f"/{canonical}</loc>" in sitemap


def test_all_content_and_download_links_resolve() -> None:
    client = TestClient(app)
    urls = {"/", "/blog", "/about", "/faq", "/contact", "/privacy", "/terms"}
    urls.update("/" + slug for slug in seo_content.TOOL_PAGES)
    urls.update("/blog/" + slug for slug in blog_content.GUIDES)
    discovered: set[str] = set()
    for url in sorted(urls):
        response = client.get(url)
        assert response.status_code == 200, url
        assert "{{" not in response.text, url
        parser = Links()
        parser.feed(response.text)
        discovered.update(parser.urls)
    for url in sorted(discovered - urls):
        if url.startswith("/api/"):
            continue
        assert client.get(url).status_code == 200, url


def test_no_false_unlimited_license_or_accuracy_claims_in_rendered_content() -> None:
    client = TestClient(app)
    pages = [client.get("/" + slug).text for slug in seo_content.TOOL_PAGES]
    pages += [client.get("/" + slug).text for slug in ("about", "faq", "privacy", "terms")]
    pages += [client.get("/blog/" + slug).text for slug in blog_content.GUIDES]
    for body in pages:
        assert not re.search(r"MIT.{0,30}Apache|no daily limits|free with no limits|never gets blurry|text stays perfect|every claim.*verifi", body, re.I)
    assert "AGPLv3" in client.get("/about").text
    assert "premium access" in client.get("/ocr-pdf").text


def test_guide_dates_and_structured_data_agree() -> None:
    client = TestClient(app)
    for slug, guide in blog_content.GUIDES.items():
        response = client.get("/blog/" + slug)
        blocks = re.findall(r'<script type="application/ld\+json">(.*?)</script>', response.text, re.S)
        article = next(obj for obj in map(json.loads, blocks) if obj["@type"] == "Article")
        assert article["datePublished"] <= article["dateModified"]
        assert article["dateModified"] == guide["date"]
        assert f'datetime="{guide["date"]}"' in response.text
        assert "independent expert review" not in response.text or "no external expert review" in response.text
