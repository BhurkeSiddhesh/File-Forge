"""Server-rendered SEO landing pages for File Forge tools.

Every tool gets a dedicated, fully-rendered HTML page (title, meta, H1, body and
FAQ are all present in the *raw* response — no JavaScript required), which is what
both Google and JS-less AI crawlers (GPTBot, ClaudeBot, PerplexityBot, ...) need.

Adding a new tool page is a one-line entry in ``TOOL_PAGES`` below. ``main.py``
serves these via the catch-all ``/{slug}`` route and lists them in ``sitemap.xml``.

The rendered HTML keeps the literal placeholders ``{{BASE_URL}}``,
``{{ADSENSE_HEAD}}`` and ``{{ADSENSE_SLOT}}`` — ``main.py`` substitutes them at
request time (mirroring the existing ``_render_page`` mechanism), so this module
has no dependency on runtime configuration and stays trivially unit-testable.
"""
from __future__ import annotations

import html
import json
import re
from typing import Dict, List, Tuple

from scripts.tool_extra import extra_html

# --- constants -------------------------------------------------------------

ASSET_V = "20260623"
SITE = "File Forge"
GITHUB = "https://github.com/BhurkeSiddhesh/File-Forge"

# Literal tokens substituted by main.py. Defined as plain strings (NOT inside an
# f-string) so the braces survive into the rendered output verbatim.
BASE = "{{BASE_URL}}"
ADS_HEAD = "{{ADSENSE_HEAD}}"
ADS_SLOT = "{{ADSENSE_SLOT}}"
CONSENT_BANNER = "{{CONSENT_BANNER}}"
SITE_VERIFY = "{{SITE_VERIFICATION}}"
CF_ANALYTICS = "{{CF_ANALYTICS}}"

# First-party page-view beacon for the server-rendered landing pages (which don't
# load script.js). Posts a single anonymous page_view to /api/track — the same
# first-party funnel endpoint the home app uses. No file data, cookies-only the
# anonymous ff_sid the server sets. Best-effort and silent on any failure.
FUNNEL_BEACON = (
    "<script>(function(){try{"
    "var p=JSON.stringify({event:'page_view',label:location.pathname||'/'});"
    "var u='/api/track';"
    "if(navigator.sendBeacon){navigator.sendBeacon(u,new Blob([p],{type:'application/json'}));}"
    "else{fetch(u,{method:'POST',body:p,keepalive:true,"
    "headers:{'Content-Type':'application/json'},credentials:'same-origin'});}"
    "}catch(e){}})();</script>"
)

# category -> (deep-link tool param, human label)
CATEGORIES = {
    "pdf": "PDF Tools",
    "image": "Image Tools",
    "excel": "Excel Tools",
    "ppt": "PowerPoint Tools",
    "word": "Word Tools",
}

_TAG_RE = re.compile(r"<[^>]+>")


def _plain(s: str) -> str:
    """Strip HTML tags + unescape entities — for use inside JSON-LD text."""
    return html.unescape(_TAG_RE.sub("", s)).strip()


def _attr(s: str) -> str:
    """Escape a value destined for an HTML attribute (title/meta/og)."""
    return html.escape(s, quote=True)


# --- tool catalogue --------------------------------------------------------
# Each entry: title, meta, h1, lede, tool (deep-link category), app
# (SoftwareApplication name), cta, how (H2 heading), steps[], benefits[] (raw
# HTML), faqs[] (question, answer-HTML), related[] (slugs).

TOOL_PAGES: Dict[str, dict] = {
    # ===================== PDF =====================
    "unlock-pdf": {
        "title": "Unlock PDF: Remove PDF Password Online Free | File Forge",
        "meta": "Remove the password from a PDF you own, free and online. No signup, no watermarks, open source. Your file is deleted automatically after download.",
        "h1": "Unlock PDF: Remove a PDF Password Online",
        "lede": "Got a PDF that asks for a password every single time you open it: a bank statement, salary slip, or insurance document? Enter the password once, and download an unlocked copy that opens instantly, forever.",
        "tool": "pdf", "app": "Unlock PDF", "cta": "Unlock a PDF now, free",
        "how": "How to remove a PDF password",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Remove Password</strong> and type the document's current password.",
            "Download the unlocked PDF. The original and the result are deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Actually private:</strong> files are deleted right after download. And unlike closed-source tools that just claim this, our <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">entire source code is public on GitHub</a>, so anyone can verify it or run their own copy.",
            "<strong>Completely free:</strong> no trial limits, no watermarks, no “premium” upsell.",
            "<strong>No signup:</strong> no account, no email, no tracking of your documents.",
        ],
        "faqs": [
            ("Is it legal to remove a password from a PDF?", "Yes, if you own the document or have permission to access it. You must know the current password. File Forge does not crack or guess passwords; it re-saves the file without encryption after you provide the correct password."),
            ("Is my PDF stored on your server?", "No. Files are deleted immediately after download, and anything left over is purged automatically within an hour. Because the project is open source, this isn't a promise you have to take on faith: you can read the code."),
            ("Do I need an account?", "No. No signup, no email, no watermark. Just upload, unlock, download."),
        ],
        "related": ["pdf-to-word", "compress-pdf", "extract-pdf-pages", "merge-pdf", "protect-pdf"],
    },
    "pdf-to-word": {
        "title": "PDF to Word Converter: Free Online, No Signup | File Forge",
        "meta": "Convert PDF to an editable Word (DOCX), free online. Keeps text, images and layout. No signup, no watermarks, open source. Files deleted automatically.",
        "h1": "PDF to Word Converter: Free &amp; Online",
        "lede": "Turn any PDF into an editable Word (DOCX) document in seconds. Fix a typo in a contract, reuse a report, or edit a form, all without retyping a single line.",
        "tool": "pdf", "app": "PDF to Word", "cta": "Convert PDF to Word, free",
        "how": "How to convert PDF to Word",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Convert to Word</strong>. (If the PDF is locked, <a href=\"/unlock-pdf\">unlock it</a> first.)",
            "Download your editable DOCX. Both files are deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>No paywall games:</strong> many converters give you one free file and then ask for a credit card. File Forge is free, every time.",
            "<strong>Verifiably private:</strong> files are deleted after download, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">full source code is on GitHub</a>: you don't have to trust a marketing claim.",
            "<strong>Handles locked PDFs:</strong> <a href=\"/unlock-pdf\">remove the password</a> first, then convert; both tools are free.",
        ],
        "faqs": [
            ("Will my PDF's formatting be preserved in Word?", "For digitally-created PDFs, standard conversion preserves text, images, and most layouts well. Documents with complex tables or multi-column layouts convert best with the AI Layout Recovery option, where available on the server."),
            ("Can I convert a password-protected PDF to Word?", "Yes, first <a href=\"/unlock-pdf\">remove the password</a> (you'll need to know it), then convert the unlocked PDF to Word."),
            ("Is the PDF to Word converter really free?", "Yes. No page limits per file, no daily paywall, no watermark, no account. You can even self-host the whole tool from GitHub."),
        ],
        "related": ["unlock-pdf", "compress-pdf", "extract-pdf-pages", "pdf-to-text", "word-to-pdf"],
    },
    "compress-pdf": {
        "title": "Compress PDF Online Free: Reduce PDF File Size | File Forge",
        "meta": "Shrink PDF file size online, free. Three compression levels, no Acrobat needed, no signup, no watermarks. Open source. Files auto-deleted after download.",
        "h1": "Compress PDF: Reduce PDF File Size Online",
        "lede": "PDF too big to email, or over a portal's upload limit? Compress it in seconds: pick Low, Medium, or High compression and see exactly how much space you saved.",
        "tool": "pdf", "app": "Compress PDF", "cta": "Compress a PDF now, free",
        "how": "How to compress a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Compress PDF</strong> and pick a level: Low (best quality), Medium (balanced), or High (smallest size).",
            "Download the compressed file: we show you the original size, new size, and percentage saved.",
        ],
        "benefits": [
            "<strong>No Acrobat Pro needed:</strong> compression runs on our free server, nothing to install.",
            "<strong>Verifiably private:</strong> your file is deleted right after download. The <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>, so this is checkable, not just a claim.",
            "<strong>Free with no limits:</strong> no daily quota, no watermark, no signup.",
        ],
        "faqs": [
            ("How much smaller will my PDF get?", "PDFs full of photos or scanned pages often shrink by 50–90% at the High level. Text-only PDFs are already efficient and may shrink only slightly. You'll see the exact before/after numbers on screen."),
            ("Will compression make my PDF blurry?", "Text always stays sharp: compression mainly resamples images. Use Low if image quality matters most, High if file size matters most."),
            ("Can I compress a password-protected PDF?", "Yes, first <a href=\"/unlock-pdf\">remove the password</a> (you'll need to know it), then compress the unlocked file."),
        ],
        "related": ["merge-pdf", "pdf-to-word", "extract-pdf-pages", "unlock-pdf", "compress-image"],
    },
    "extract-pdf-pages": {
        "title": "Extract Pages from PDF: Split PDF Online Free | File Forge",
        "meta": "Pull specific pages or page ranges out of a PDF into a new file, free. Type 1,3,5-10 and download. No signup, open source, files deleted automatically.",
        "h1": "Extract Pages from a PDF: Split PDFs Online",
        "lede": "Need just the invoice from a 40-page statement, or one chapter from a long report? Extract exactly the pages you want into a clean new PDF. No software, no signup.",
        "tool": "pdf", "app": "Extract PDF Pages", "cta": "Extract PDF pages, free",
        "how": "How to extract pages from a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Extract Pages</strong> and type the pages you want, e.g. <code>1,3,5-10</code>.",
            "Download a new PDF containing only those pages. Your upload is deleted automatically.",
        ],
        "benefits": [
            "<strong>Flexible page selection:</strong> mix single pages and ranges in one go (<code>2,7,12-15</code>).",
            "<strong>Verifiably private:</strong> files are deleted right after download, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">source code is public</a>, so you can confirm exactly what happens to your document.",
            "<strong>Free forever:</strong> no watermark, no account, no daily limit.",
        ],
        "faqs": [
            ("How do I specify which pages to extract?", "Commas for single pages, dashes for ranges: <code>1,3,5-10</code> gives you page 1, page 3, and pages 5 through 10 in a single new PDF."),
            ("Does extracting pages change the original PDF?", "No, you get a brand-new file with just the selected pages. The original stays exactly as it was on your device."),
            ("Can I extract pages from a password-protected PDF?", "Yes, first <a href=\"/unlock-pdf\">remove the password</a> (you'll need to know it), then extract pages from the unlocked file."),
        ],
        "related": ["split-pdf", "merge-pdf", "organize-pdf", "compress-pdf", "pdf-to-word"],
    },
    "pdf-to-text": {
        "title": "PDF to Text: Extract Text from PDF Free | File Forge",
        "meta": "Extract all text from a PDF into a clean TXT file, free and online. OCR fallback for scanned documents. No signup, open source, files deleted automatically.",
        "h1": "PDF to Text: Extract Text from Any PDF",
        "lede": "Copy-pasting from a PDF gives you broken lines and garbage characters. Get the whole document as a clean, plain text file instead, with OCR fallback for scanned pages.",
        "tool": "pdf", "app": "PDF to Text", "cta": "Extract PDF text, free",
        "how": "How to convert PDF to text",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Extract Text</strong>. Toggle “preserve line breaks” to taste.",
            "Download the .txt file. Your PDF is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Works on scans:</strong> OCR fallback recognizes text in scanned documents that normal extractors return empty.",
            "<strong>Verifiably private:</strong> automatic deletion after download, with the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">full source code on GitHub</a> to prove it.",
            "<strong>Free and anonymous:</strong> no signup, no watermark, no limits.",
        ],
        "faqs": [
            ("Can I extract text from a scanned PDF?", "Yes, when the PDF has no embedded text layer, the OCR fallback recognizes the text from the page images, where available on the server."),
            ("Will the text keep its formatting?", "Your choice: preserve line breaks and spacing to mirror the document, or disable it for continuous text that's easier to paste elsewhere."),
            ("What output do I get?", "A plain .txt file: perfect for searching, quoting, summarizing, or feeding into other tools."),
        ],
        "related": ["pdf-to-word", "pdf-to-excel", "extract-pdf-pages", "compress-pdf", "unlock-pdf"],
    },
    "merge-pdf": {
        "title": "Merge PDF: Combine PDF Files Online Free | File Forge",
        "meta": "Combine multiple PDFs into one file, free online. Reorder before merging, no signup, no watermarks. Open source. Files auto-deleted after download.",
        "h1": "Merge PDF: Combine Multiple PDFs Into One",
        "lede": "Joining a cover letter, résumé, and certificates into a single application? Combine any number of PDFs into one clean document, in the order you choose. Free, with no software to install.",
        "tool": "pdf", "app": "Merge PDF", "cta": "Combine PDF files, free",
        "how": "How to merge PDF files",
        "steps": [
            "Open the PDF tools and choose <strong>Merge PDFs</strong>.",
            "Select two or more PDFs in the upload area (multi-select is enabled).",
            "Click Merge and download the single combined PDF. Every uploaded file is deleted automatically.",
        ],
        "benefits": [
            "<strong>Unlimited combining:</strong> merge as many PDFs as you need: no two-file free cap.",
            "<strong>Verifiably private:</strong> your files are deleted right after download, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a> so you can confirm it.",
            "<strong>Free, no signup:</strong> no account, no watermark stamped across your pages.",
        ],
        "faqs": [
            ("How many PDFs can I merge at once?", "As many as you like in a single pass: select them all in the upload area. There's no artificial two-file limit."),
            ("Can I choose the order of the merged pages?", "Yes, the files are combined in the order you select them, so arrange them the way you want the final document to read."),
            ("Can I merge a password-protected PDF?", "Remove the password first with the free <a href=\"/unlock-pdf\">Unlock PDF</a> tool, then merge the unlocked copy with your other files."),
        ],
        "related": ["compress-pdf", "extract-pdf-pages", "organize-pdf", "split-pdf", "pdf-to-word"],
    },
    "split-pdf": {
        "title": "Split PDF: Separate PDF Pages Online Free | File Forge",
        "meta": "Split a PDF into the pages you need, free and online. Pull out single pages or ranges like 1,3,5-10 into a new file. No signup, open source, files auto-deleted.",
        "h1": "Split PDF: Separate the Pages You Need",
        "lede": "One giant PDF when you only need a few pages? Split out exactly the pages or ranges you want into a fresh document: a receipt, a single chapter, one signed page. Free and private.",
        "tool": "pdf", "app": "Split PDF", "cta": "Split a PDF now, free",
        "how": "How to split a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Extract Pages</strong> and enter the pages or ranges to keep, e.g. <code>1,3,5-10</code>.",
            "Download the new, smaller PDF. The original upload is deleted automatically.",
        ],
        "benefits": [
            "<strong>Precise control:</strong> single pages, ranges, or any mix: split out only what matters.",
            "<strong>Reorder while you split:</strong> need the pages rearranged too? Use <a href=\"/organize-pdf\">Organize PDF</a>.",
            "<strong>Verifiably private &amp; free:</strong> files deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How is splitting different from extracting pages?", "They're the same operation here: you choose which pages go into the new PDF. Enter <code>1,3,5-10</code> to keep just those pages."),
            ("Can I split one PDF into several separate files?", "Run the tool once per range you want as its own file, e.g. extract <code>1-5</code>, then <code>6-10</code>, to produce two documents."),
            ("Will the rest of my document be affected?", "No, your original is never modified. You only ever get a new file with the pages you chose."),
        ],
        "related": ["extract-pdf-pages", "merge-pdf", "organize-pdf", "compress-pdf", "pdf-to-jpg"],
    },
    "rotate-pdf": {
        "title": "Rotate PDF: Turn PDF Pages Online Free | File Forge",
        "meta": "Rotate PDF pages 90, 180 or 270 degrees online, free. Fix sideways scans permanently. Rotate all pages or just some. No signup, open source, files auto-deleted.",
        "h1": "Rotate PDF: Fix Sideways or Upside-Down Pages",
        "lede": "Scanned a document and it came out sideways? Permanently rotate every page, or just the ones that are wrong, so your PDF always opens the right way up.",
        "tool": "pdf", "app": "Rotate PDF", "cta": "Rotate a PDF now, free",
        "how": "How to rotate a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Rotate PDF</strong>, pick an angle (90°, 180° or 270°), and optionally list specific pages.",
            "Download the corrected PDF. The rotation is saved into the file. Your upload is deleted automatically.",
        ],
        "benefits": [
            "<strong>Permanent fix:</strong> the rotation is baked into the document, not just a temporary view.",
            "<strong>Rotate some or all pages:</strong> leave the page field blank for the whole file, or list pages like <code>1,3-5</code>.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Can I rotate only certain pages?", "Yes, enter the page numbers (e.g. <code>1,3-5</code>) to rotate just those, or leave it blank to rotate every page."),
            ("Is the rotation permanent?", "Yes, it's written into the PDF, so the file always opens correctly oriented, on any device."),
            ("Does rotating reduce quality?", "No, rotation simply changes the page orientation flag and content matrix; nothing is re-compressed."),
        ],
        "related": ["organize-pdf", "extract-pdf-pages", "compress-pdf", "merge-pdf", "rotate-image"],
    },
    "protect-pdf": {
        "title": "Protect PDF: Add a Password Online Free | File Forge",
        "meta": "Add a password to a PDF online, free. Encrypt with a user password and set print/copy permissions. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "Protect PDF: Add a Password to Your PDF",
        "lede": "Sending something confidential: a contract, payslip, or ID? Lock the PDF with a password so only people who know it can open it, and decide whether printing or copying is allowed.",
        "tool": "pdf", "app": "Protect PDF", "cta": "Password-protect a PDF, free",
        "how": "How to password-protect a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Protect PDF</strong>, set a user password, and pick what's allowed (printing, copying, editing).",
            "Download the encrypted PDF. Your original upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Real encryption:</strong> the file is encrypted, not just “hidden”; the password is required to open it.",
            "<strong>Permission control:</strong> separately allow or block printing, copying text, and editing.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no account.",
        ],
        "faqs": [
            ("What's the difference between the user and owner password?", "The user password is required to open the document. The optional owner password controls permissions (like editing) without being needed just to view the file."),
            ("Can I remove the password later?", "Yes, as long as you know it, use the free <a href=\"/unlock-pdf\">Unlock PDF</a> tool to produce an unprotected copy."),
            ("Is my password stored anywhere?", "No. It's used only to encrypt your file during processing, and your upload is deleted right after download. The <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a> so you can verify this."),
        ],
        "related": ["unlock-pdf", "watermark-pdf", "compress-pdf", "sign-pdf", "merge-pdf"],
    },
    "watermark-pdf": {
        "title": "Watermark PDF: Add a Watermark Online Free | File Forge",
        "meta": "Stamp a text watermark across every page of a PDF, free. Choose position and opacity (e.g. DRAFT, CONFIDENTIAL). No signup, open source, files auto-deleted.",
        "h1": "Add a Watermark to a PDF",
        "lede": "Mark a document as DRAFT, CONFIDENTIAL, or with your name across every page. Add a text watermark with the position and transparency you choose. It's free, and no software is needed.",
        "tool": "pdf", "app": "Watermark PDF", "cta": "Add a PDF watermark, free",
        "how": "How to watermark a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Add Watermark</strong>, type your text, and set the position and opacity.",
            "Download the watermarked PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Every page covered:</strong> the watermark is applied across the whole document in one pass.",
            "<strong>Adjustable look:</strong> diagonal or straight, faint or bold: you control position and opacity.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Can I control how strong the watermark looks?", "Yes, set the opacity so it's a faint background mark or a bold overlay, and choose diagonal, top, center, or bottom placement."),
            ("Will the watermark cover my content?", "A low-opacity diagonal watermark stays readable over your text. Pick the opacity that balances visibility with legibility."),
            ("Can I watermark images too?", "Yes, use the free <a href=\"/watermark-image\">Add Watermark to Image</a> tool for JPG, PNG and WebP files."),
        ],
        "related": ["protect-pdf", "sign-pdf", "pdf-page-numbers", "compress-pdf", "watermark-image"],
    },
    "pdf-to-jpg": {
        "title": "PDF to JPG: Convert PDF Pages to Images Free | File Forge",
        "meta": "Convert each page of a PDF into a JPG or PNG image, free. Choose the resolution; download a zip. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "PDF to JPG: Turn PDF Pages Into Images",
        "lede": "Need your PDF pages as images for a slide, a website, or a quick preview? Render every page to a crisp JPG or PNG at the quality you choose, and download them all in one zip.",
        "tool": "pdf", "app": "PDF to JPG", "cta": "Convert PDF to JPG, free",
        "how": "How to convert a PDF to JPG",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>PDF → JPG</strong>, then pick a resolution (72/150/300 DPI) and format (JPG or PNG).",
            "Download a zip with one image per page. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Quality you control:</strong> 72 DPI for small previews up to 300 DPI for print-sharp images.",
            "<strong>JPG or PNG:</strong> JPG for small photo-like pages, PNG for crisp text and line art.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("What resolution should I pick?", "150 DPI is a good balance for screens. Choose 300 DPI if you'll print the images, or 72 DPI for tiny, fast-loading previews."),
            ("Do I get one image per page?", "Yes, every page becomes its own image, and they're bundled into a single zip for download."),
            ("Can I go the other way, images to PDF?", "Yes, use the free <a href=\"/image-to-pdf\">Image to PDF</a> tool to turn photos into a PDF."),
        ],
        "related": ["image-to-pdf", "pdf-to-powerpoint", "compress-pdf", "extract-pdf-pages", "pdf-to-excel"],
    },
    "pdf-page-numbers": {
        "title": "Add Page Numbers to PDF: Free Online | File Forge",
        "meta": "Add page numbers to a PDF, free. Choose position, format (1/i/A), start number and pages to skip. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "Add Page Numbers to a PDF",
        "lede": "Submitting a report, thesis, or legal bundle that needs numbered pages? Add clean page numbers in the position and style you want, and skip the cover page if you need to.",
        "tool": "pdf", "app": "Add Page Numbers", "cta": "Add page numbers, free",
        "how": "How to add page numbers to a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Add Page Numbers</strong>, then set position, number format, start value, and pages to skip.",
            "Download the numbered PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Flexible formats:</strong> decimal (1, 2, 3), roman (i, ii, iii), or letters (A, B, C).",
            "<strong>Skip the cover:</strong> start numbering after the title page, and choose any start number.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Can I start numbering from a page other than the first?", "Yes, set how many leading pages to skip (e.g. a cover) and the starting number, so numbering begins exactly where you want."),
            ("Where can the numbers go?", "Any of six positions: bottom or top, left, center, or right."),
            ("Can I use roman numerals?", "Yes, choose decimal, roman, or alphabetical numbering."),
        ],
        "related": ["watermark-pdf", "organize-pdf", "merge-pdf", "compress-pdf", "sign-pdf"],
    },
    "pdf-to-excel": {
        "title": "PDF to Excel: Extract Tables to XLSX Free | File Forge",
        "meta": "Convert PDF tables to an editable Excel (.xlsx) spreadsheet, free. No signup, no watermarks, open source. Your file is deleted automatically after download.",
        "h1": "PDF to Excel: Extract Tables to a Spreadsheet",
        "lede": "Stop retyping tables out of PDFs. Pull the tabular data from a PDF into an editable Excel workbook so you can sort, total, and chart it in minutes.",
        "tool": "pdf", "app": "PDF to Excel", "cta": "Convert PDF to Excel, free",
        "how": "How to convert PDF to Excel",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>PDF → Excel</strong> to detect and extract the tables.",
            "Download the .xlsx workbook. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>No retyping:</strong> get your numbers into cells instead of copying them by hand.",
            "<strong>Editable output:</strong> a real .xlsx you can sort, filter, and calculate with.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How well does it detect tables?", "Clean, grid-like tables from digitally-created PDFs convert best. Very irregular layouts or scans may need a little cleanup afterward."),
            ("What if my PDF is a scan?", "Scanned tables without a text layer are harder to extract. Try the <a href=\"/pdf-to-text\">PDF to Text</a> tool with OCR if table detection comes up short."),
            ("Is it free?", "Yes, no signup, no watermark, no limits, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["pdf-to-text", "pdf-to-word", "excel-to-pdf", "pdf-to-powerpoint", "compress-pdf"],
    },
    "pdf-to-powerpoint": {
        "title": "PDF to PowerPoint: Convert PDF to PPTX Free | File Forge",
        "meta": "Convert a PDF into a PowerPoint (.pptx) presentation online, free. Each page becomes a slide. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "PDF to PowerPoint: Convert PDF to Slides",
        "lede": "Turn a PDF into a presentation in one step: each page becomes a slide you can drop straight into PowerPoint, Keynote, or Google Slides.",
        "tool": "pdf", "app": "PDF to PowerPoint", "cta": "Convert PDF to PPTX, free",
        "how": "How to convert PDF to PowerPoint",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>PDF → PowerPoint</strong> and pick a quality level.",
            "Download the .pptx file. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>One slide per page:</strong> your PDF's layout is preserved as full-page slide images.",
            "<strong>Drops in anywhere:</strong> the .pptx opens in PowerPoint, Keynote, and Google Slides.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Will the slides be editable text?", "Each page is placed as a high-quality image on its slide, which preserves the exact layout. For editable text, try <a href=\"/pdf-to-word\">PDF to Word</a> instead."),
            ("What quality should I choose?", "150 DPI is a good default for on-screen presenting; choose higher if you'll project on a large screen."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["pdf-to-jpg", "powerpoint-to-pdf", "pdf-to-word", "pdf-to-excel", "compress-pdf"],
    },
    "sign-pdf": {
        "title": "Sign PDF: Add a Signature to a PDF Free | File Forge",
        "meta": "Add a signature image to a PDF online, free. Place your signature on any page and position. No signup, no watermarks, open source, files deleted automatically.",
        "h1": "Sign PDF: Stamp Your Signature on a Document",
        "lede": "Sign a contract or form without printing it. Upload a picture of your signature, drop it on the right page and corner, and download a signed PDF. Free and private.",
        "tool": "pdf", "app": "Sign PDF", "cta": "Sign a PDF now, free",
        "how": "How to sign a PDF",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Sign PDF</strong>, upload your signature image (a transparent PNG works best), and pick the page, position and size.",
            "Download the signed PDF. Both files are deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>No printing &amp; scanning:</strong> sign digitally and keep the document clean.",
            "<strong>Precise placement:</strong> choose the page, corner, and width so your signature lands exactly right.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("What signature image should I use?", "A PNG with a transparent background looks best, so only the ink shows. A photo of a signature on white paper also works."),
            ("Can I place it on a specific page?", "Yes, choose the exact page number and the corner (or center) where the signature should sit, plus its width."),
            ("Is my document private?", "Yes, both your PDF and signature image are deleted right after download, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["protect-pdf", "watermark-pdf", "pdf-page-numbers", "merge-pdf", "unlock-pdf"],
    },
    "organize-pdf": {
        "title": "Organize PDF: Reorder & Delete Pages Free | File Forge",
        "meta": "Reorder, delete, or duplicate PDF pages online, free. Set a new page order in one step. No signup, no watermarks, open source, files deleted automatically.",
        "h1": "Organize PDF: Reorder, Delete &amp; Duplicate Pages",
        "lede": "Pages in the wrong order, or a few you want gone? Set a new page order in one go: rearrange, drop unwanted pages, or duplicate the ones you need twice.",
        "tool": "pdf", "app": "Organize PDF", "cta": "Organize a PDF now, free",
        "how": "How to reorder PDF pages",
        "steps": [
            "Upload your PDF (drag &amp; drop or browse).",
            "Choose <strong>Organize PDF</strong> and type the new page order, e.g. <code>3,1,2</code>. Repeat a number to duplicate; omit one to delete it.",
            "Download the reorganized PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Three actions in one:</strong> reorder, delete, and duplicate pages with a single list.",
            "<strong>Simple syntax:</strong> <code>3,1,2,1</code> means page 3, then 1, then 2, then 1 again.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How do I delete a page?", "Just leave its number out of the order list: any page you don't mention is dropped from the result."),
            ("How do I duplicate a page?", "List its number more than once. For example <code>1,1,2</code> repeats page 1 before page 2."),
            ("Does this change my original file?", "No, you always get a new PDF, and your uploaded copy is deleted automatically."),
        ],
        "related": ["merge-pdf", "extract-pdf-pages", "split-pdf", "rotate-pdf", "pdf-page-numbers"],
    },
    # ===================== Image =====================
    "heic-to-jpeg": {
        "title": "HEIC to JPG Converter: Free Online, No Signup | File Forge",
        "meta": "Convert iPhone HEIC/HEIF photos to JPG, free. Adjustable quality, no signup, no watermarks. Open source. Photos are deleted automatically after download.",
        "h1": "HEIC to JPG: Convert iPhone Photos Online",
        "lede": "iPhone photos saved as .HEIC won't open on your Windows PC, can't be uploaded to that web form, and confuse older software. Convert them to universally compatible JPG in seconds.",
        "tool": "image", "app": "HEIC to JPG", "cta": "Convert HEIC to JPG, free",
        "how": "How to convert HEIC to JPG",
        "steps": [
            "Upload your .heic or .heif photo (drag &amp; drop or browse).",
            "Pick a JPEG quality (95% default, visually identical) and click <strong>Convert to JPEG</strong>.",
            "Download your JPG. The original is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Your photos stay yours:</strong> deleted immediately after download. And because the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>, that's verifiable, not a marketing line.",
            "<strong>Quality control:</strong> choose the exact JPEG quality instead of accepting a fixed setting.",
            "<strong>Free, no signup:</strong> no account, no watermark, no daily cap.",
        ],
        "faqs": [
            ("Why won't my HEIC photos open on Windows or Android?", "HEIC has been Apple's default photo format since iOS 11. Many Windows PCs, Android phones, and websites can't read it without extra codecs. JPG works everywhere."),
            ("Will converting HEIC to JPG lose quality?", "At the default 95% setting the difference is invisible in normal use. Lower the slider for smaller files."),
            ("Are my photos kept on your server?", "No, they're deleted right after download, with an automatic sweep for anything left behind."),
        ],
        "related": ["resize-image", "compress-image", "convert-image", "image-to-pdf", "crop-image"],
    },
    "resize-image": {
        "title": "Resize Image: Pixels, Percent or Target KB | File Forge",
        "meta": "Resize images online for free: exact width/height, percentage scale, or a target file size in KB. Crop visually too. No signup, open source, files auto-deleted.",
        "h1": "Resize Image Online: Pixels, Percent, or Target KB",
        "lede": "“Photo must be under 200 KB.” “Image must be exactly 800×600.” Whatever the requirement, resize any image to exact dimensions, a percentage, or a target file size, and crop it visually if needed.",
        "tool": "image", "app": "Resize Image", "cta": "Resize an image now, free",
        "how": "How to resize an image",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Pick a mode: exact <strong>dimensions</strong>, <strong>percentage</strong> scale, or <strong>target file size</strong> in KB.",
            "Download the resized image. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Target-KB mode:</strong> made for government portals, job applications, and exam forms that reject photos over a size limit.",
            "<strong>Visual cropper included:</strong> drag handles to <a href=\"/crop-image\">crop</a> exactly what you need before or after resizing.",
            "<strong>Verifiably private:</strong> images are deleted after download: the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a> so you can check, or self-host.",
        ],
        "faqs": [
            ("Can I resize an image to a specific file size in KB?", "Yes, choose Target File Size mode and enter your limit (e.g. 200 KB). The tool adjusts the image to fit under it."),
            ("What image formats are supported?", "JPG, PNG, WebP, and iPhone HEIC/HEIF photos."),
            ("Can I crop too?", "Yes, <a href=\"/crop-image\">Crop mode</a> gives you a visual drag-and-drop editor."),
        ],
        "related": ["crop-image", "compress-image", "convert-image", "heic-to-jpeg", "image-to-pdf"],
    },
    "image-to-pdf": {
        "title": "Image to PDF: Convert JPG/PNG to PDF Free | File Forge",
        "meta": "Convert images (JPG, PNG, WebP, HEIC) to a PDF online, free. Choose page size and fit. No signup, no watermarks, open source, files deleted automatically.",
        "h1": "Image to PDF: Convert Photos to a PDF",
        "lede": "Turn a photo, scan, or screenshot into a tidy PDF: perfect for uploading an ID, receipt, or homework where only PDFs are accepted. Choose the page size and how the image fits.",
        "tool": "image", "app": "Image to PDF", "cta": "Convert image to PDF, free",
        "how": "How to convert an image to PDF",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Choose <strong>Image → PDF</strong>, then pick the page size (A4, Letter, or auto) and fit mode.",
            "Download the PDF. Your uploaded image is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Made for uploads:</strong> many portals only accept PDFs: convert your photo in one step.",
            "<strong>Fit your way:</strong> fit the image neatly to a page, or keep its original size.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Which image formats can I convert?", "JPG, PNG, WebP, and Apple HEIC/HEIF photos can all be turned into a PDF."),
            ("Can I pick the page size?", "Yes, A4 or Letter, or “auto” to size the page to the image itself."),
            ("Can I go the other way?", "Yes, use <a href=\"/pdf-to-jpg\">PDF to JPG</a> to turn PDF pages back into images."),
        ],
        "related": ["pdf-to-jpg", "heic-to-jpeg", "compress-image", "resize-image", "merge-pdf"],
    },
    "compress-image": {
        "title": "Compress Image: Reduce JPG/PNG Size Free | File Forge",
        "meta": "Compress JPG, PNG and WebP images online, free. Shrink file size with an adjustable quality slider. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "Compress Image: Reduce Photo File Size",
        "lede": "Photos too heavy to email or slowing down your website? Compress them to a fraction of the size with a quality slider you control. Free, with no signup and no watermark.",
        "tool": "image", "app": "Compress Image", "cta": "Compress an image, free",
        "how": "How to compress an image",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Choose <strong>Compress</strong> and set the quality: lower means a smaller file.",
            "Download the smaller image. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>You control the trade-off:</strong> slide between maximum quality and minimum size.",
            "<strong>Faster sites &amp; emails:</strong> smaller images load quicker and slip under attachment limits.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How small can the file get?", "It depends on the image, but photos often shrink dramatically at a moderate quality setting with little visible difference."),
            ("Do you support PNG and WebP?", "Yes, JPG, PNG, WebP and HEIC are all accepted. To switch formats, use <a href=\"/convert-image\">Convert Image</a>."),
            ("Is the original kept?", "No, your upload is deleted right after download. The <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a> so you can verify it."),
        ],
        "related": ["resize-image", "convert-image", "crop-image", "compress-pdf", "image-to-pdf"],
    },
    "convert-image": {
        "title": "Convert Image: JPG, PNG, WebP Converter Free | File Forge",
        "meta": "Convert images between JPG, PNG and WebP, free. Adjustable quality, no signup, no watermarks. Open source. Files auto-deleted after download.",
        "h1": "Convert Image: JPG ↔ PNG ↔ WebP",
        "lede": "Need a PNG instead of a JPG, or a lightweight WebP for your website? Convert between the common image formats in one click, with the quality you choose.",
        "tool": "image", "app": "Convert Image", "cta": "Convert an image, free",
        "how": "How to convert an image format",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Choose <strong>Convert Format</strong>, pick the target (JPG, PNG, or WebP), and set quality if relevant.",
            "Download the converted image. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>All the common formats:</strong> move freely between JPG, PNG, and WebP.",
            "<strong>WebP for the web:</strong> get smaller, faster-loading images for your site.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Which conversions are supported?", "Any combination of JPG, PNG, and WebP. For Apple HEIC specifically, the dedicated <a href=\"/heic-to-jpeg\">HEIC to JPG</a> tool is the simplest route."),
            ("When should I use WebP?", "WebP usually produces smaller files than JPG or PNG at similar quality, which is great for websites and faster page loads."),
            ("Does converting reduce quality?", "Converting to a lossless format like PNG preserves quality; for JPG/WebP you set the quality level yourself."),
        ],
        "related": ["compress-image", "resize-image", "heic-to-jpeg", "crop-image", "image-to-pdf"],
    },
    "crop-image": {
        "title": "Crop Image Online Free: Visual Crop Tool | File Forge",
        "meta": "Crop images online for free with a visual drag-and-drop editor. Trim JPG, PNG, WebP and HEIC photos. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "Crop Image: Trim Photos Visually",
        "lede": "Cut out the background, fix the framing, or grab just one part of a photo. Drag the handles to crop exactly what you want and download the result. Free and private.",
        "tool": "image", "app": "Crop Image", "cta": "Crop an image now, free",
        "how": "How to crop an image",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Switch to <strong>Crop</strong> mode and drag the handles over the area you want to keep.",
            "Click Crop and download the result. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Visual editor:</strong> see exactly what you'll get before you crop: no guessing pixel coordinates.",
            "<strong>Works with resizing:</strong> combine with <a href=\"/resize-image\">Resize Image</a> to hit an exact size after cropping.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Is the crop done visually?", "Yes, a drag-and-drop editor lets you frame the crop box over the image and preview the result."),
            ("What formats can I crop?", "JPG, PNG, WebP, and Apple HEIC/HEIF photos."),
            ("Can I resize after cropping?", "Yes, use <a href=\"/resize-image\">Resize Image</a> to set exact dimensions or a target file size."),
        ],
        "related": ["resize-image", "compress-image", "convert-image", "rotate-image", "heic-to-jpeg"],
    },
    "rotate-image": {
        "title": "Rotate Image Online Free: Turn Photos | File Forge",
        "meta": "Rotate images 90, 180 or 270 degrees online, free. Fix sideways phone photos in one click. No signup, no watermarks, open source, files deleted automatically.",
        "h1": "Rotate Image: Fix Sideways Photos",
        "lede": "Phone photo came out sideways or upside down? Rotate it 90°, 180°, or 270° and download the corrected image. Free, no app to install.",
        "tool": "image", "app": "Rotate Image", "cta": "Rotate an image now, free",
        "how": "How to rotate an image",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Choose <strong>Rotate</strong> and pick an angle: 90°, 180°, or 270°.",
            "Download the rotated image. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>One-click fix:</strong> straighten a sideways photo instantly.",
            "<strong>No quality loss fuss:</strong> rotate in clean 90° steps with the orientation baked in.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Which angles can I rotate by?", "90° (counter-clockwise), 180°, or 270°: enough to fix any sideways or upside-down photo."),
            ("What formats are supported?", "JPG, PNG, WebP, and Apple HEIC/HEIF photos."),
            ("Need to rotate a PDF instead?", "Use the free <a href=\"/rotate-pdf\">Rotate PDF</a> tool for documents."),
        ],
        "related": ["crop-image", "resize-image", "compress-image", "rotate-pdf", "convert-image"],
    },
    "watermark-image": {
        "title": "Watermark Image: Add Text to a Photo Free | File Forge",
        "meta": "Add a text watermark to an image online, free. Choose position, color and opacity. No signup, no watermarks of ours, open source, files deleted automatically.",
        "h1": "Add a Watermark to an Image",
        "lede": "Protect a photo or brand it with your name. Stamp text onto any image with the position, color, and opacity you choose. It's free, and we never add a watermark of our own.",
        "tool": "image", "app": "Watermark Image", "cta": "Watermark an image, free",
        "how": "How to watermark an image",
        "steps": [
            "Upload your image (JPG, PNG, WebP, or HEIC).",
            "Choose <strong>Add Watermark</strong>, type your text, and set position, color, and opacity.",
            "Download the watermarked image. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Full styling control:</strong> place it in any corner, center, or diagonally, in the color and opacity you want.",
            "<strong>No forced branding:</strong> the only watermark on your image is the one you add.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Can I choose where the watermark goes?", "Yes, corners, center, or a diagonal stamp across the image, with adjustable color and opacity."),
            ("Will File Forge add its own watermark?", "Never. Your output carries only the text you choose: nothing else."),
            ("Can I watermark a PDF?", "Yes, use the free <a href=\"/watermark-pdf\">Watermark PDF</a> tool for documents."),
        ],
        "related": ["watermark-pdf", "compress-image", "resize-image", "convert-image", "crop-image"],
    },
    # ===================== Excel =====================
    "excel-to-pdf": {
        "title": "Excel to PDF: Convert XLSX to PDF Online Free | File Forge",
        "meta": "Convert Excel spreadsheets (XLSX/XLS) to PDF online, free. Every sheet rendered as a styled table. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "Excel to PDF: Convert Spreadsheets to PDF",
        "lede": "Share a spreadsheet that looks the same on every device. Convert your Excel workbook to a clean PDF, with each sheet rendered as a tidy table. Free and without Office installed.",
        "tool": "excel", "app": "Excel to PDF", "cta": "Convert Excel to PDF, free",
        "how": "How to convert Excel to PDF",
        "steps": [
            "Upload your Excel file (.xlsx or .xls) or CSV.",
            "Choose <strong>Excel → PDF</strong>.",
            "Download the PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Consistent everywhere:</strong> a PDF looks identical on any screen, no Excel required to view it.",
            "<strong>Every sheet included:</strong> each worksheet is rendered as its own styled table.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Will my formatting be preserved exactly?", "Layout is best-effort: cell colors, merged cells, and charts are approximated. Plain data tables convert very cleanly."),
            ("Can I convert a CSV too?", "Yes, CSV files are accepted. You can also turn a CSV into a workbook first with <a href=\"/csv-to-xlsx\">CSV to XLSX</a>."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["csv-to-xlsx", "xlsx-to-csv", "merge-excel", "pdf-to-excel", "word-to-pdf"],
    },
    "csv-to-xlsx": {
        "title": "CSV to Excel: Convert CSV to XLSX Online Free | File Forge",
        "meta": "Convert a CSV file into an Excel workbook (.xlsx) online, free. Pick the delimiter (comma, semicolon, tab, pipe). No signup, open source, files auto-deleted.",
        "h1": "CSV to Excel: Turn a CSV Into a Workbook",
        "lede": "Got a raw CSV export that's awkward to read? Convert it into a proper Excel (.xlsx) workbook, with the right delimiter, so you can format, filter, and chart it.",
        "tool": "excel", "app": "CSV to XLSX", "cta": "Convert CSV to Excel, free",
        "how": "How to convert CSV to Excel",
        "steps": [
            "Upload your .csv file (drag &amp; drop or browse).",
            "Choose <strong>CSV → XLSX</strong> and select the delimiter (comma, semicolon, tab, or pipe).",
            "Download the .xlsx workbook. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Handles tricky delimiters:</strong> European semicolons, tabs, and pipes, not just commas.",
            "<strong>Real workbook output:</strong> a native .xlsx you can style and add formulas to.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("My CSV uses semicolons; will that work?", "Yes, pick the semicolon delimiter (common in European exports). Tab and pipe are supported too."),
            ("Can I go back to CSV later?", "Yes, use <a href=\"/xlsx-to-csv\">XLSX to CSV</a> to export a sheet back to CSV."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["xlsx-to-csv", "excel-to-pdf", "merge-excel", "pdf-to-excel", "word-to-pdf"],
    },
    "xlsx-to-csv": {
        "title": "Excel to CSV: Convert XLSX to CSV Online Free | File Forge",
        "meta": "Export an Excel sheet to CSV online, free. Choose which sheet to export. No signup, no watermarks, open source. Your file is auto-deleted after download.",
        "h1": "Excel to CSV: Export a Sheet to CSV",
        "lede": "Need plain CSV for an import, a database, or a script? Export any sheet of your Excel workbook to a clean CSV file. Free, no Office, no signup.",
        "tool": "excel", "app": "XLSX to CSV", "cta": "Convert Excel to CSV, free",
        "how": "How to convert Excel to CSV",
        "steps": [
            "Upload your Excel file (.xlsx or .xls).",
            "Choose <strong>XLSX → CSV</strong> and name the sheet to export (or leave blank for the first one).",
            "Download the .csv file. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Pick the sheet:</strong> export exactly the worksheet you need, not the whole book.",
            "<strong>Import-ready:</strong> clean CSV that databases, scripts, and other tools accept.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Can I choose which worksheet to export?", "Yes, enter the sheet name, or leave it blank to export the first sheet."),
            ("Need to convert the other way?", "Use <a href=\"/csv-to-xlsx\">CSV to XLSX</a> to turn a CSV into an Excel workbook."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["csv-to-xlsx", "excel-to-pdf", "merge-excel", "pdf-to-excel", "word-to-pdf"],
    },
    "merge-excel": {
        "title": "Merge Excel: Combine Workbooks Online Free | File Forge",
        "meta": "Combine multiple Excel (.xlsx) workbooks into one online, free. No signup, no watermarks, open source. Your files are deleted automatically after download.",
        "h1": "Merge Excel: Combine Multiple Workbooks",
        "lede": "Several spreadsheets that belong together? Combine multiple Excel workbooks into a single file. Free, no Office needed, nothing left on our servers.",
        "tool": "excel", "app": "Merge Excel", "cta": "Merge Excel files, free",
        "how": "How to merge Excel workbooks",
        "steps": [
            "Choose <strong>Merge Workbooks</strong> in the Excel tools.",
            "Select two or more .xlsx files in the upload area.",
            "Download the combined workbook. Every uploaded file is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Many files at once:</strong> combine several workbooks in a single pass.",
            "<strong>No Office required:</strong> merge in the browser: nothing to install.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How many workbooks can I merge?", "Select as many .xlsx files as you need in the upload area and combine them in one step."),
            ("What happens to the sheets?", "The worksheets from your files are brought together into a single combined workbook."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["excel-to-pdf", "csv-to-xlsx", "xlsx-to-csv", "merge-pdf", "pdf-to-excel"],
    },
    # ===================== PowerPoint =====================
    "powerpoint-to-pdf": {
        "title": "PowerPoint to PDF: Convert PPT to PDF Free | File Forge",
        "meta": "Convert a PowerPoint (.pptx) presentation to PDF online, free. Slides rendered into a clean PDF. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "PowerPoint to PDF: Convert Slides to PDF",
        "lede": "Share a deck that opens anywhere and can't be accidentally edited. Convert your PowerPoint presentation into a clean PDF. Free, no Office required.",
        "tool": "ppt", "app": "PowerPoint to PDF", "cta": "Convert PPT to PDF, free",
        "how": "How to convert PowerPoint to PDF",
        "steps": [
            "Upload your .pptx presentation (drag &amp; drop or browse).",
            "Choose <strong>PPT → PDF</strong>.",
            "Download the PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Opens everywhere:</strong> a PDF needs no PowerPoint to view and looks the same on any device.",
            "<strong>Locks the layout:</strong> recipients see your slides exactly as designed.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Will animations and transitions be kept?", "No, a PDF is static, so each slide becomes a page. Layout is best-effort; gradients, SmartArt, and animations aren't preserved."),
            ("Can I turn slides into images instead?", "Yes, use <a href=\"/ppt-to-images\">PPT to Images</a> to get a PNG or JPG per slide."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["ppt-to-images", "merge-ppt", "pdf-to-powerpoint", "word-to-pdf", "excel-to-pdf"],
    },
    "ppt-to-images": {
        "title": "PPT to Images: PowerPoint to PNG/JPG Free | File Forge",
        "meta": "Convert each PowerPoint slide to a PNG or JPG image online, free. Download all slides as a zip. No signup, no watermarks, open source, files auto-deleted.",
        "h1": "PPT to Images: Each Slide as a PNG or JPG",
        "lede": "Need your slides as images for a thumbnail, a doc, or social media? Render every PowerPoint slide to a PNG or JPG and download them all in one zip. Free and private.",
        "tool": "ppt", "app": "PPT to Images", "cta": "Convert PPT to images, free",
        "how": "How to convert PowerPoint to images",
        "steps": [
            "Upload your .pptx presentation (drag &amp; drop or browse).",
            "Choose <strong>PPT → Images</strong> and pick PNG or JPG.",
            "Download a zip with one image per slide. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>One image per slide:</strong> bundled into a single zip for easy download.",
            "<strong>PNG or JPG:</strong> PNG for crisp text, JPG for smaller files.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("What format should I choose?", "PNG keeps text and shapes razor-sharp; JPG makes smaller files for photo-heavy slides."),
            ("Do I get every slide?", "Yes, each slide is rendered to its own image and zipped together."),
            ("Prefer a single PDF?", "Use <a href=\"/powerpoint-to-pdf\">PowerPoint to PDF</a> to get all slides in one document."),
        ],
        "related": ["powerpoint-to-pdf", "merge-ppt", "pdf-to-jpg", "pdf-to-powerpoint", "image-to-pdf"],
    },
    "merge-ppt": {
        "title": "Merge PowerPoint: Combine PPTX Online Free | File Forge",
        "meta": "Combine multiple PowerPoint (.pptx) presentations into one, free. No signup, no watermarks, open source. Your files are auto-deleted after download.",
        "h1": "Merge PowerPoint: Combine Presentations",
        "lede": "Stitch several decks into one seamless presentation. Combine multiple PowerPoint files in the order you choose. Free, no Office, nothing kept on our servers.",
        "tool": "ppt", "app": "Merge PowerPoint", "cta": "Merge PowerPoint files, free",
        "how": "How to merge PowerPoint files",
        "steps": [
            "Choose <strong>Merge PPTX</strong> in the PowerPoint tools.",
            "Select two or more .pptx files in the upload area.",
            "Download the combined presentation. Every uploaded file is deleted automatically.",
        ],
        "benefits": [
            "<strong>Many decks, one file:</strong> combine several presentations into a single .pptx.",
            "<strong>Your order:</strong> the slides follow the order you add the files.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("How many presentations can I merge?", "Select as many .pptx files as you need in the upload area and merge them in one pass."),
            ("Can I control the slide order?", "Yes, the combined deck follows the order in which you add the files."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["powerpoint-to-pdf", "ppt-to-images", "merge-pdf", "pdf-to-powerpoint", "merge-excel"],
    },
    # ===================== Word =====================
    "word-to-pdf": {
        "title": "Word to PDF: Convert DOCX to PDF Online Free | File Forge",
        "meta": "Convert a Word document (DOCX) to PDF, free. Keeps your layout and fonts. No signup, no watermarks, open source. Files auto-deleted after download.",
        "h1": "Word to PDF: Convert DOCX to PDF",
        "lede": "Send a document that looks identical everywhere and can't be accidentally edited. Convert your Word (.docx) file to a polished PDF. Free, no Microsoft Office required.",
        "tool": "word", "app": "Word to PDF", "cta": "Convert Word to PDF, free",
        "how": "How to convert Word to PDF",
        "steps": [
            "Upload your Word document (.docx).",
            "Choose <strong>Word → PDF</strong>.",
            "Download the PDF. Your upload is deleted from our server automatically.",
        ],
        "benefits": [
            "<strong>Pixel-stable sharing:</strong> a PDF preserves your layout and fonts on every device.",
            "<strong>No Office needed:</strong> convert in the browser: nothing to install or buy.",
            "<strong>Free &amp; verifiably private:</strong> deleted after download, <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">open source</a>, no signup.",
        ],
        "faqs": [
            ("Will my formatting stay the same?", "Layout, headings, and fonts are preserved for standard documents. Very complex Word features may shift slightly."),
            ("Can I convert back to Word?", "Yes, use the free <a href=\"/pdf-to-word\">PDF to Word</a> tool to get an editable DOCX again."),
            ("Is it free?", "Yes, no signup, no watermark, and the <a href=\"" + GITHUB + "\" target=\"_blank\" rel=\"noopener\">code is open source</a>."),
        ],
        "related": ["pdf-to-word", "excel-to-pdf", "powerpoint-to-pdf", "compress-pdf", "merge-pdf"],
    },
}


# --- rendering -------------------------------------------------------------

def _jsonld(obj: dict) -> str:
    return '<script type="application/ld+json">\n' + json.dumps(obj, indent=2, ensure_ascii=False) + "\n</script>"


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


def _software_schema(slug: str, page: dict) -> dict:
    # NOTE: intentionally no aggregateRating/review — fabricating ratings without
    # a real, on-page, user-generated review mechanism violates Google's
    # structured-data policy and risks a manual action. Add them only once
    # genuine reviews exist. The publisher/sameAs/inLanguage fields below are
    # legitimate entity signals that help Google associate the tool with the
    # File Forge brand and its GitHub presence.
    return {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": page["app"] + " | " + SITE,
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "Any (web browser)",
        "url": BASE + "/" + slug,
        "description": page["meta"],
        "inLanguage": "en",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "publisher": {
            "@type": "Organization",
            "name": SITE,
            "url": BASE + "/",
            "sameAs": [GITHUB],
        },
    }


def _howto_schema(page: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "HowTo",
        "name": _plain(page["h1"]),
        "step": [
            {"@type": "HowToStep", "position": i + 1, "text": _plain(s)}
            for i, s in enumerate(page["steps"])
        ],
    }


def _breadcrumb_schema(slug: str, page: dict) -> dict:
    return {
        "@context": "https://schema.org",
        "@type": "BreadcrumbList",
        "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": SITE, "item": BASE + "/"},
            {"@type": "ListItem", "position": 2, "name": _plain(page["app"]),
             "item": BASE + "/" + slug},
        ],
    }


def _related_html(related: List[str]) -> str:
    links = []
    for r in related:
        target = TOOL_PAGES.get(r)
        if target:
            links.append('<a href="/' + r + '">' + target["app"] + "</a>")
    return " · ".join(links)


def _security_section(page: dict) -> str:
    """A short, server-rendered privacy note woven around the specific tool
    (``page['app']``).

    Kept deliberately concise (~90 words). The old version was ~300 words of
    near-identical prose repeated across all 32 tool pages, which diluted each
    page's unique content and raised a duplicate-content signal on a young
    domain. The full privacy architecture now lives on the dedicated /privacy
    page (linked below); each tool page instead spends its word budget on
    tool-specific steps/benefits/FAQs. Rendered into raw HTML so JS-less AI
    crawlers still read it.
    """
    app = page["app"]
    return f"""        <h2>Is the {app} tool private?</h2>
        <p>Yes. Your file is uploaded over encrypted HTTPS, processed, handed
            back, and then <strong>deleted</strong> &mdash; the upload goes the moment the
            {app} operation finishes and the result the instant you download it, with
            an hourly sweeper as a backstop. Unlike closed tools that just <em>claim</em>
            they don't keep your files, {SITE}'s
            <a href="{GITHUB}" target="_blank" rel="noopener">code is fully open source</a>,
            so you can verify exactly how the {app} tool handles your data &mdash; or self-host it.
            No account, no watermark, no upsell. See our
            <a href="/privacy">privacy details</a> for the full picture.</p>"""


# Renders into render_tool_page below, between the benefits and FAQ sections.


def render_tool_page(slug: str) -> str:
    """Render a full HTML page for ``slug``. Returns HTML with the literal
    placeholders ``{{BASE_URL}}``/``{{ADSENSE_HEAD}}``/``{{ADSENSE_SLOT}}`` left
    intact for ``main.py`` to substitute."""
    page = TOOL_PAGES[slug]
    og_title = page["title"].split(" | ")[0]
    og_desc = page["meta"]

    steps_html = "\n".join("            <li>" + s + "</li>" for s in page["steps"])
    benefits_html = "\n".join("            <li>" + b + "</li>" for b in page["benefits"])
    faq_html = "\n".join(
        "        <h3>" + _plain(q) + "</h3>\n        <p>" + a + "</p>"
        for q, a in page["faqs"]
    )

    schema_blocks = "\n".join([
        _jsonld(_faq_schema(page["faqs"])),
        _jsonld(_software_schema(slug, page)),
        _jsonld(_howto_schema(page)),
        _jsonld(_breadcrumb_schema(slug, page)),
    ])

    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {SITE_VERIFY}
    <title>{_attr(page['title'])}</title>
    <meta name="description" content="{_attr(page['meta'])}">
    <link rel="canonical" href="{BASE}/{slug}">
    <meta name="robots" content="index, follow, max-image-preview:large, max-snippet:-1, max-video-preview:-1">
    <meta name="theme-color" content="#ffffff">
    <meta property="og:type" content="website">
    <meta property="og:site_name" content="{SITE}">
    <meta property="og:title" content="{_attr(og_title)}">
    <meta property="og:description" content="{_attr(og_desc)}">
    <meta property="og:url" content="{BASE}/{slug}">
    <meta property="og:image" content="{BASE}/static/og-image.png">
    <meta property="og:image:width" content="1200">
    <meta property="og:image:height" content="630">
    <meta property="og:image:alt" content="{_attr(og_title)}">
    <meta name="twitter:card" content="summary_large_image">
    <meta name="twitter:title" content="{_attr(og_title)}">
    <meta name="twitter:description" content="{_attr(og_desc)}">
    <meta name="twitter:image" content="{BASE}/static/og-image.png">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="preconnect" href="https://cdnjs.cloudflare.com" crossorigin>
    <link rel="stylesheet" href="/static/style.css?v={ASSET_V}">
    {ADS_HEAD}
    {CF_ANALYTICS}
{schema_blocks}
</head>

<body class="seo-page">
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>
    <main class="page-wrap">
        <nav class="page-nav"><a href="/">&larr; {SITE}: all tools</a></nav>

        <h1>{page['h1']}</h1>
        <p class="lede">{page['lede']}</p>

        <p><a class="cta" href="/?tool={page['tool']}">{page['cta']}</a></p>

        {ADS_SLOT}

        <h2>{page['how']}</h2>
        <ol>
{steps_html}
        </ol>

        <h2>Why use {SITE}?</h2>
        <ul>
{benefits_html}
        </ul>

{extra_html(slug)}

{_security_section(page)}

        <h2>Frequently asked questions</h2>
{faq_html}

        <h2>More free tools</h2>
        <p>{_related_html(page['related'])}</p>

        <footer class="page-footer">
            <a href="/">Home</a> · <a href="/blog">Guides</a> · <a href="/about">About</a> · <a href="/faq">FAQ</a> · <a href="/contact">Contact</a>
            · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a
                href="{GITHUB}" target="_blank" rel="noopener">GitHub</a>
        </footer>
    </main>
    {CONSENT_BANNER}
    {FUNNEL_BEACON}
</body>

</html>
"""


def render_404_page() -> str:
    """Branded hard-404 body. Served with HTTP status 404 by main.py."""
    popular = ["merge-pdf", "compress-pdf", "pdf-to-word", "unlock-pdf",
               "heic-to-jpeg", "image-to-pdf", "excel-to-pdf", "word-to-pdf"]
    links = "\n".join(
        '            <li><a href="/' + s + '">' + TOOL_PAGES[s]["app"] + "</a></li>"
        for s in popular if s in TOOL_PAGES
    )
    return f"""<!DOCTYPE html>
<html lang="en">

<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Page not found (404) | {SITE}</title>
    <meta name="robots" content="noindex">
    <link rel="icon" type="image/svg+xml" href="/static/favicon.svg">
    <link rel="stylesheet" href="/static/style.css?v={ASSET_V}">
</head>

<body class="seo-page">
    <div class="background-blobs">
        <div class="blob blob-1"></div>
        <div class="blob blob-2"></div>
    </div>
    <main class="page-wrap">
        <nav class="page-nav"><a href="/">&larr; {SITE}: all tools</a></nav>
        <h1>404: Page not found</h1>
        <p class="lede">That page doesn't exist (or moved). All {SITE} tools are free, with no signup and files
            deleted automatically. Try one of these popular tools:</p>
        <ul>
{links}
        </ul>
        <p><a class="cta" href="/">Go to all File Forge tools</a></p>
        <footer class="page-footer">
            <a href="/">Home</a> · <a href="/about">About</a> · <a href="/faq">FAQ</a> · <a href="/contact">Contact</a>
            · <a href="/privacy">Privacy</a> · <a href="/terms">Terms</a> · <a
                href="{GITHUB}" target="_blank" rel="noopener">GitHub</a>
        </footer>
    </main>
</body>

</html>
"""


# Slug -> sitemap priority. Home is handled separately in main.py.
def all_tool_slugs() -> List[str]:
    return list(TOOL_PAGES.keys())
