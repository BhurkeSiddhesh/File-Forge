"""Server-rendered /blog guides — long-tail SEO content.

Mirrors the pattern in ``seo_content.py`` (same <head>, canonical, funnel beacon,
consent banner, JSON-LD) but for editorial how-to guides rather than tool pages.
The point is to rank for informational long-tail queries ("how to compress a PDF
without losing quality") that the transactional tool pages don't target, and to
funnel that traffic into the matching tool via prominent in-content CTAs.

Each guide is fully server-rendered HTML (no JS needed) so JS-less crawlers and
AI bots read the whole article from the raw response. main.py substitutes the
{{BASE_URL}}/{{ADSENSE_*}}/{{CONSENT_BANNER}}/{{SITE_VERIFICATION}}/{{CF_ANALYTICS}}
tokens at request time, exactly as for tool pages.

To add a guide: append an entry to GUIDES. `primary_tool` must be a real slug in
seo_content.TOOL_PAGES; `date` is an ISO date used for Article dateModified and
should be bumped when the content meaningfully changes.
"""
from __future__ import annotations

from typing import Dict, List, Tuple

from scripts import seo_content as sc
from scripts.seo_content import (
    ASSET_V, SITE, GITHUB, BASE, ADS_HEAD, ADS_SLOT, CONSENT_BANNER,
    SITE_VERIFY, CF_ANALYTICS, FUNNEL_BEACON, TOOL_PAGES,
    _attr, _plain, _jsonld,
)

BLOG_BASE = BASE + "/blog"

# --- guide data ------------------------------------------------------------
# Each guide: title/meta (head), h1/dek (hero), body (list of (h2, html_body)),
# faqs (list of (q, a)), primary_tool (slug -> the tool this guide funnels to),
# related (extra tool slugs to cross-link), date (ISO, for dateModified).
GUIDES: Dict[str, dict] = {
    "how-to-compress-a-pdf-without-losing-quality": {
        "title": "How to Compress a PDF Without Losing Quality (Free) | " + SITE,
        "meta": ("Compress a PDF to a smaller file size without making it blurry. "
                 "A free, step-by-step guide plus the trade-offs that actually "
                 "affect quality — no signup, no watermark."),
        "h1": "How to compress a PDF without losing quality",
        "dek": ("Big PDF won't attach to an email or upload to a portal? Here's how "
                "to shrink it while keeping text sharp and images readable — and what "
                "“quality” really means when you compress."),
        "primary_tool": "compress-pdf",
        "related": ["merge-pdf", "split-pdf", "pdf-to-word"],
        "date": "2026-07-20",
        "body": [
            ("Why PDFs get so large", (
                "<p>Most oversized PDFs are heavy for one of three reasons: "
                "high-resolution scanned images, embedded fonts, or pages exported "
                "at print resolution (300+ DPI) when screen resolution (72–150 "
                "DPI) would look identical on a monitor. Text itself is tiny; it's "
                "almost always the images driving the file size.</p>")),
            ("The fastest way: compress it online", (
                "<p>You don't need to install anything. Use the free "
                "<a href=\"/compress-pdf\">Compress PDF</a> tool: it re-samples "
                "oversized images and strips redundant data while leaving text as "
                "crisp vector glyphs, so the words stay perfectly sharp.</p>"
                "<ol>"
                "<li>Open <a href=\"/compress-pdf\">Compress PDF</a>.</li>"
                "<li>Drag in your file (it's processed on our server over HTTPS and "
                "deleted right after — nothing is kept).</li>"
                "<li>Download the smaller PDF. Compare it to the original before you "
                "send it.</li>"
                "</ol>")),
            ("What “without losing quality” really means", (
                "<p>Compression is a trade-off, so it helps to know where quality "
                "actually lives:</p>"
                "<ul>"
                "<li><strong>Text stays perfect.</strong> Vector text is re-saved "
                "losslessly — it never gets blurry no matter how much you "
                "compress.</li>"
                "<li><strong>Images degrade gracefully.</strong> Photos are "
                "re-encoded; moderate compression is invisible on screen, and you "
                "only notice softening if you zoom far in or print at high DPI.</li>"
                "<li><strong>Match the destination.</strong> Emailing or uploading to "
                "a web portal? Screen-resolution compression is ideal. Sending to a "
                "commercial printer? Keep the original.</li>"
                "</ul>")),
            ("Extra ways to shrink a PDF", (
                "<p>If one pass isn't small enough:</p>"
                "<ul>"
                "<li><strong>Remove pages you don't need</strong> with "
                "<a href=\"/split-pdf\">Split PDF</a> before compressing.</li>"
                "<li><strong>Combine smartly.</strong> If you merged several files, "
                "compress the final PDF once at the end rather than each part.</li>"
                "<li><strong>Scanned document?</strong> A scan is really a stack of "
                "images, so it benefits the most from compression.</li>"
                "</ul>")),
        ],
        "faqs": [
            ("Will compressing a PDF make the text blurry?",
             "No. Text in a PDF is stored as vector glyphs and is re-saved without "
             "loss, so it stays sharp at any zoom. Only embedded images are "
             "re-encoded, and moderate compression is invisible on screen."),
            ("How small can I make a PDF?",
             "It depends on what's inside. Image-heavy or scanned PDFs can often drop "
             "50–90%. A text-only PDF is already small, so there's less to save."),
            ("Is it safe to compress a confidential PDF here?",
             "Yes. The file is sent over encrypted HTTPS, processed, returned, and "
             "then deleted — with an hourly sweeper as a backstop. File Forge is "
             "open source, so you can verify exactly how it's handled."),
        ],
    },
    "how-to-convert-pdf-to-word-for-free": {
        "title": "How to Convert a PDF to Word (DOCX) for Free | " + SITE,
        "meta": ("Turn a PDF into an editable Word document for free. Step-by-step, "
                 "with tips on keeping layout and tables intact and when a scanned "
                 "PDF needs OCR. No signup, no watermark."),
        "h1": "How to convert a PDF to an editable Word document",
        "dek": ("Need to edit a PDF but only have the finished file? Convert it to a "
                "Word .docx you can open in Microsoft Word, Google Docs, or "
                "LibreOffice — here's how, and how to keep the formatting."),
        "primary_tool": "pdf-to-word",
        "related": ["compress-pdf", "merge-pdf", "unlock-pdf"],
        "date": "2026-07-20",
        "body": [
            ("Convert your PDF to Word in three steps", (
                "<p>Use the free <a href=\"/pdf-to-word\">PDF to Word</a> tool — "
                "no account and no software install:</p>"
                "<ol>"
                "<li>Open <a href=\"/pdf-to-word\">PDF to Word</a> and drop in your "
                "PDF.</li>"
                "<li>It reconstructs paragraphs, headings, and tables into a real "
                ".docx (not just an image pasted into a page).</li>"
                "<li>Download the Word file and edit it anywhere — Word, Google "
                "Docs, or LibreOffice.</li>"
                "</ol>")),
            ("How to keep the layout intact", (
                "<p>Conversion quality depends on how the PDF was made:</p>"
                "<ul>"
                "<li><strong>Digital PDFs</strong> (exported from Word, a browser, or "
                "a design tool) convert cleanly — text, headings, and simple "
                "tables usually survive.</li>"
                "<li><strong>Complex multi-column layouts</strong> may need light "
                "clean-up after conversion; expect to fix the odd spacing or column "
                "break.</li>"
                "<li><strong>Locked PDFs</strong> must be unlocked first — run "
                "them through <a href=\"/unlock-pdf\">Unlock PDF</a> if you have the "
                "password.</li>"
                "</ul>")),
            ("Scanned PDFs and OCR", (
                "<p>If your PDF is a scan or photo of a document, the “text” "
                "is really an image, so it can't be edited until it's recognised. "
                "Optical character recognition (OCR) reads the pixels and turns them "
                "back into selectable, editable text. File Forge runs OCR fully "
                "offline on our server, so scanned pages come back as words you can "
                "actually change.</p>")),
        ],
        "faqs": [
            ("Can I convert a scanned PDF to editable Word?",
             "Yes. A scan is an image, so it's run through OCR (optical character "
             "recognition) first to turn the picture of text back into editable text "
             "before it's written into the Word document."),
            ("Will my tables and formatting survive?",
             "Digital PDFs keep paragraphs, headings, and simple tables well. Very "
             "complex or multi-column layouts may need minor clean-up after "
             "converting — that's normal for any PDF-to-Word conversion."),
            ("Is it really free with no watermark?",
             "Yes. No signup, no watermark, no “one free file” limit. File "
             "Forge is open source and your upload is deleted right after "
             "processing."),
        ],
    },
    "how-to-convert-heic-to-jpg": {
        "title": "How to Convert HEIC to JPG for Free (iPhone Photos) | " + SITE,
        "meta": ("iPhone photos won't open on Windows or in your app? Convert HEIC to "
                 "JPG for free. Why HEIC exists, and a step-by-step fix — no "
                 "signup, no watermark, photos deleted after."),
        "h1": "How to convert HEIC (iPhone photos) to JPG",
        "dek": ("Shared an iPhone photo and the other person can't open it? That's "
                "HEIC. Here's how to convert it to a universally supported JPG in "
                "seconds — and why your phone saves this format in the first "
                "place."),
        "primary_tool": "heic-to-jpeg",
        "related": ["image-to-pdf"],
        "date": "2026-07-20",
        "body": [
            ("What is HEIC, and why won't it open?", (
                "<p>HEIC (High Efficiency Image Container) is the format modern "
                "iPhones use by default. It stores the same photo at roughly half the "
                "file size of JPG, which is great for your phone's storage — but "
                "many Windows apps, older devices, web forms, and messaging tools "
                "still don't recognise it, so the photo appears broken or won't "
                "upload.</p>")),
            ("Convert HEIC to JPG in seconds", (
                "<p>The free <a href=\"/heic-to-jpeg\">HEIC to JPG</a> tool converts "
                "them without any app:</p>"
                "<ol>"
                "<li>Open <a href=\"/heic-to-jpeg\">HEIC to JPG</a>.</li>"
                "<li>Drop in your <code>.heic</code> file (straight from an iPhone or "
                "AirDrop).</li>"
                "<li>Download a standard <code>.jpg</code> that opens everywhere — "
                "Windows, Android, email, and every website upload box.</li>"
                "</ol>")),
            ("Stop your iPhone saving HEIC (optional)", (
                "<p>If you'd rather your phone just shoot JPG going forward: open "
                "<strong>Settings → Camera → Formats</strong> and choose "
                "<strong>Most Compatible</strong>. New photos will save as JPG. Your "
                "existing HEIC library still needs converting — that's what the "
                "tool above is for.</p>")),
            ("Turning photos into a PDF instead", (
                "<p>Sometimes the real goal is a single document, not loose images. "
                "Once your photos are JPGs you can combine them into one file with "
                "<a href=\"/image-to-pdf\">Image to PDF</a> — handy for receipts, "
                "IDs, or a set of scanned pages.</p>")),
        ],
        "faqs": [
            ("Why do my iPhone photos have a .heic extension?",
             "Newer iPhones save photos as HEIC by default because it stores the same "
             "image quality at about half the size of JPG. The trade-off is that many "
             "non-Apple apps and sites don't support it yet."),
            ("Does converting HEIC to JPG reduce quality?",
             "There's a small, usually invisible re-encoding step because JPG is a "
             "different codec. For everyday sharing, printing, and uploads the result "
             "looks identical to the original."),
            ("Are my photos uploaded anywhere permanent?",
             "No. Each photo is processed over HTTPS and deleted immediately after "
             "conversion, with an hourly sweeper as a backstop. Nothing is stored or "
             "used to train anything."),
        ],
    },
}


def guide_slugs() -> List[str]:
    return list(GUIDES.keys())


# --- schema ----------------------------------------------------------------

def _article_schema(slug: str, g: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "Article",
        "headline": _plain(g["h1"]),
        "description": g["meta"],
        "inLanguage": "en",
        "mainEntityOfPage": {"@type": "WebPage", "@id": BLOG_BASE + "/" + slug},
        "dateModified": g["date"],
        "datePublished": g["date"],
        "author": {"@type": "Organization", "name": SITE, "url": BASE + "/"},
        "publisher": {
            "@type": "Organization",
            "name": SITE,
            "url": BASE + "/",
            "sameAs": [GITHUB],
        },
    }


def _breadcrumb_schema(slug: str, g: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE, "item": BASE + "/"},
            {"@type": "ListItem", "position": 2, "name": "Guides", "item": BLOG_BASE},
            {"@type": "ListItem", "position": 3, "name": _plain(g["h1"]),
             "item": BLOG_BASE + "/" + slug},
        ],
    }


def _faq_schema(faqs: List[Tuple[str, str]]) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "FAQPage",
        "mainEntity": [
            {"@type": "Question", "name": _plain(q),
             "acceptedAnswer": {"@type": "Answer", "text": _plain(a)}}
            for q, a in faqs
        ],
    }


def _related_tools_html(slugs: List[str]) -> str:
    links = []
    for s in slugs:
        t = TOOL_PAGES.get(s)
        if t:
            links.append('<a href="/' + s + '">' + t["app"] + "</a>")
    return " · ".join(links)


_HEAD = """<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {site_verify}
    <title>{title}</title>
    <meta name="description" content="{meta}">
    <link rel="canonical" href="{canonical}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <meta name="theme-color" content="#ffffff">
    <meta property="og:type" content="{og_type}">
    <meta property="og:site_name" content="{site}">
    <meta property="og:title" content="{og_title}">
    <meta property="og:description" content="{og_desc}">
    <meta property="og:url" content="{canonical}">
    <meta property="og:image" content="{base}/static/og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{og_title}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{og_title}">
    <meta name="twitter:description" content="{og_desc}">
    <meta name="twitter:image" content="{base}/static/og-image.png">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="/static/style.css?v={asset_v}">
    {ads_head}
    {cf_analytics}
{schema_blocks}
</head>
"""


def render_guide(slug: str) -> str:
    g = GUIDES[slug]
    canonical = BLOG_BASE + "/" + slug
    og_title = g["title"].split(" | ")[0]

    schema_blocks = "\n".join([
        _jsonld(_article_schema(slug, g)),
        _jsonld(_breadcrumb_schema(slug, g)),
        _jsonld(_faq_schema(g["faqs"])),
    ])
    head = _HEAD.format(
        site_verify=SITE_VERIFY, title=_attr(g["title"]), meta=_attr(g["meta"]),
        canonical=canonical, og_type="article", site=SITE, og_title=_attr(og_title),
        og_desc=_attr(g["meta"]), base=BASE, asset_v=ASSET_V, ads_head=ADS_HEAD,
        cf_analytics=CF_ANALYTICS, schema_blocks=schema_blocks,
    )

    sections = "\n".join(
        f"        <h2>{h2}</h2>\n        {body}" for h2, body in g["body"]
    )
    faqs = "\n".join(
        "        <h3>" + _plain(q) + "</h3>\n        <p>" + a + "</p>"
        for q, a in g["faqs"]
    )
    tool = TOOL_PAGES[g["primary_tool"]]
    cta_href = "/" + g["primary_tool"]

    return f"""{head}
<body class="seo-page">
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>
    <main class="page-wrap">
        <nav class="page-nav"><a href="/blog">&larr; {SITE} Guides</a></nav>

        <h1>{g['h1']}</h1>
        <p class="lede">{g['dek']}</p>

        <p><a class="cta" href="{cta_href}">Open the free {tool['app']} tool &rarr;</a></p>

        {ADS_SLOT}

{sections}

        <h2>Frequently asked questions</h2>
{faqs}

        <h2>Related free tools</h2>
        <p>{_related_tools_html([g['primary_tool']] + g['related'])}</p>

        <footer class="page-footer">
            <a href="/">Home</a> · <a href="/blog">Guides</a> · <a href="/about">About</a>
            · <a href="/privacy">Privacy</a> · <a href="{GITHUB}" target="_blank" rel="noopener">GitHub</a>
        </footer>
    </main>
    {CONSENT_BANNER}
    {FUNNEL_BEACON}
</body>

</html>
"""


def render_blog_index() -> str:
    canonical = BLOG_BASE
    title = "Guides — How to Work With PDFs, Images & Documents | " + SITE
    meta = ("Free step-by-step guides for compressing PDFs, converting PDF to "
            "Word, turning iPhone HEIC photos into JPG, and more — from the "
            "open-source File Forge toolbox.")
    schema_blocks = _jsonld({
        "@context": "https://schema.org",
        "@type": "CollectionPage",
        "name": "File Forge Guides",
        "description": meta,
        "url": canonical,
        "inLanguage": "en",
    })
    head = _HEAD.format(
        site_verify=SITE_VERIFY, title=_attr(title), meta=_attr(meta),
        canonical=canonical, og_type="website", site=SITE, og_title=_attr(title.split(" | ")[0]),
        og_desc=_attr(meta), base=BASE, asset_v=ASSET_V, ads_head=ADS_HEAD,
        cf_analytics=CF_ANALYTICS, schema_blocks=schema_blocks,
    )
    cards = "\n".join(
        f'            <li><a href="/blog/{slug}"><strong>{_attr(g["h1"])}</strong>'
        f'<br><span>{_attr(g["meta"])}</span></a></li>'
        for slug, g in GUIDES.items()
    )
    return f"""{head}
<body class="seo-page">
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>
    <main class="page-wrap">
        <nav class="page-nav"><a href="/">&larr; {SITE} — all tools</a></nav>

        <h1>File Forge Guides</h1>
        <p class="lede">Practical, no-nonsense guides for getting file jobs done —
            each one links straight to the free tool that does it. No signup, no watermark,
            files deleted after processing.</p>

        {ADS_SLOT}

        <ul class="guide-list">
{cards}
        </ul>

        <p><a class="cta" href="/">Browse all free tools &rarr;</a></p>

        <footer class="page-footer">
            <a href="/">Home</a> · <a href="/about">About</a> · <a href="/faq">FAQ</a>
            · <a href="/privacy">Privacy</a> · <a href="{GITHUB}" target="_blank" rel="noopener">GitHub</a>
        </footer>
    </main>
    {CONSENT_BANNER}
    {FUNNEL_BEACON}
</body>

</html>
"""
