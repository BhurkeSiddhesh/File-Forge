"""The SEO landing page → tool deep link.

/admin/stats measured page_view → tool_open at 12%: visitors arrived on a tool
page from search, clicked the CTA, and landed on a *category* grid where they
had to find the tool a second time. The CTA now carries `&op=<slug>`, which
static/script.js resolves to the specific action card.

The contract spans two files that no compiler checks against each other, so
these tests hold the seam: every page's CTA must name an op script.js knows,
and every op must name a card index.html actually has.
"""
import re
from pathlib import Path

import pytest

from scripts import seo_content

STATIC = Path(__file__).resolve().parent.parent / "static"
SCRIPT_JS = (STATIC / "script.js").read_text(encoding="utf-8")
INDEX_HTML = (STATIC / "index.html").read_text(encoding="utf-8")

# `'slug': { card: 'some-btn' ... }` entries in script.js's DEEP_LINK_OPS.
_OP_RE = re.compile(r"^    '([a-z0-9-]+)': \{ card: '([a-z0-9-]+)'(?:, mode: '([a-z0-9-]+)')? \},$", re.M)
DEEP_LINK_OPS = {m.group(1): {"card": m.group(2), "mode": m.group(3)} for m in _OP_RE.finditer(SCRIPT_JS)}

ACTION_CARD_IDS = set(re.findall(r'class="action-card[^"]*" id="([a-z0-9-]+)"', INDEX_HTML))
ELEMENT_IDS = set(re.findall(r'id="([a-z0-9-]+)"', INDEX_HTML))


def test_deep_link_ops_were_parsed():
    """Guard the guards: if the DEEP_LINK_OPS format changes, these tests must
    fail loudly rather than silently asserting over an empty dict."""
    assert len(DEEP_LINK_OPS) >= 30
    assert ACTION_CARD_IDS, "no action cards found in index.html"


@pytest.mark.parametrize("slug", sorted(seo_content.TOOL_PAGES))
def test_cta_deep_links_to_the_specific_tool(slug):
    html = seo_content.render_tool_page(slug)
    cta = re.search(r'<a class="cta" href="([^"]+)"', html)
    assert cta, f"{slug} has no CTA link"
    href = cta.group(1)
    assert href == f"/?tool={seo_content.TOOL_PAGES[slug]['tool']}&amp;op={slug}", (
        f"{slug} CTA must deep-link to its own tool, got {href}"
    )


@pytest.mark.parametrize("slug", sorted(seo_content.TOOL_PAGES))
def test_every_tool_page_has_a_deep_link_target(slug):
    """A page whose op script.js doesn't know still opens the category, so this
    can't break the site — it just silently gives up the conversion win."""
    assert slug in DEEP_LINK_OPS, (
        f"{slug} has no DEEP_LINK_OPS entry in static/script.js — its CTA would "
        f"drop visitors on the category grid"
    )


@pytest.mark.parametrize("slug,op", sorted(DEEP_LINK_OPS.items()))
def test_deep_link_targets_exist_in_the_dom(slug, op):
    assert op["card"] in ACTION_CARD_IDS, f"{slug} → unknown action card {op['card']}"
    if op["mode"]:
        assert op["mode"] in ELEMENT_IDS, f"{slug} → unknown mode input {op['mode']}"


def test_no_stale_deep_link_entries():
    """An op with no page behind it is dead config that will drift."""
    assert set(DEEP_LINK_OPS) <= set(seo_content.TOOL_PAGES)


def test_cta_appears_before_the_ad_slot():
    """The CTA is the conversion action — it has to be above the fold, and the
    ad block is what would otherwise push it below on mobile."""
    html = seo_content.render_tool_page("pdf-to-word")
    assert html.index('class="cta"') < html.index(seo_content.ADS_SLOT)


def test_landing_pages_stay_javascript_free():
    """These pages rank because they render fully without JS. The deep link is a
    plain href precisely so that stays true — no script.js on landing pages."""
    html = seo_content.render_tool_page("pdf-to-word")
    assert "script.js" not in html
