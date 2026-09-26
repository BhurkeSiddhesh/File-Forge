"""Bundle the same authored help and examples for offline mobile reading.

Standard library only: this build step does not import FastAPI or converters.
"""
from __future__ import annotations

import argparse
import logging
import re
from pathlib import Path

from scripts import blog_content, seo_content

LOG = logging.getLogger(__name__)
STATIC = Path(__file__).resolve().parents[1] / "static"
INFO = ("about", "faq", "contact", "privacy", "terms")


def mobile_html(source: str, routes: dict[str, str], *, native_downloads: bool = True) -> str:
    """Keep offline content and upload handoff; omit all web tracking/ad scripts."""
    def script(match: re.Match) -> str:
        tag = match.group(0)
        if 'type="application/ld+json"' in tag or 'src="/static/seo-upload.js' in tag:
            return tag
        return ""

    source = re.sub(r"<script\b[^>]*>[\s\S]*?</script>", script, source, flags=re.I)
    source = source.replace("{{BASE_URL}}", "https://www.forgefiles.org")
    source = re.sub(r"\{\{[A-Z_]+\}\}", "", source)

    def link(match: re.Match) -> str:
        path, fragment = match.group(1), match.group(2) or ""
        return f'href="{routes.get(path, path)}{fragment}"'

    source = re.sub(r'href="(/[^"?#]*)(#[^"]*)?"', link, source)
    source = source.replace('"/static/', '"/').replace('"/?', '"/index.html?')
    if native_downloads:
        source = source.replace("</body>", '<p id="sample-status" class="sample-status" role="status" aria-live="polite"></p><script src="/content-enhance.js"></script></body>')
    return source


def export(output: Path) -> None:
    documents = {"/blog": blog_content.render_blog_index()}
    documents.update({f"/blog/{slug}": blog_content.render_guide(slug) for slug in blog_content.GUIDES})
    documents.update({f"/{slug}": seo_content.render_tool_page(slug) for slug in seo_content.TOOL_PAGES})
    documents.update({f"/{slug}": (STATIC / "pages" / f"{slug}.html").read_text(encoding="utf-8") for slug in INFO})
    routes = {path: "/content/" + path.strip("/").replace("/", "--") + ".html" for path in documents}
    routes["/"] = "/index.html"
    for path, source in documents.items():
        # Indic options are intentionally unavailable in the free mobile release.
        if path.startswith("/ocr-") and path != "/ocr-pdf":
            source = re.sub(r'<div class="upload-cta"[\s\S]*?</div>',
                            '<p class="processing-note">This mobile release offers English OCR. The language-specific option described here is not available in this app.</p><p><a href="/ocr-pdf">Open English OCR help</a></p>', source, count=1)
        dest = output / routes[path].lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(mobile_html(source, routes), encoding="utf-8")
    # Preserve the main app's scripts; only rewrite internal help navigation.
    index = output / "index.html"
    text = index.read_text(encoding="utf-8")
    for route, target in sorted(routes.items(), key=lambda item: -len(item[0])):
        text = text.replace(f'href="{route}"', f'href="{target}"')
    index.write_text(text, encoding="utf-8")
    LOG.info("Bundled %s offline help pages with shared examples", len(documents))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    export(args.output.resolve())
