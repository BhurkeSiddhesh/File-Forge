"""Tool-specific extended content for landing pages.

WHY: every tool page shares the same short privacy note and the same
"Why use File Forge?" benefits. To rank, each page also needs *unique*,
substantial, on-topic copy — supported formats, real limits, concrete
use-cases, and honest comparisons. That lives here, keyed by tool slug, and is
rendered by seo_content.render_tool_page between the benefits list and the
privacy note.

This is intentionally modular and incremental: a slug with no entry here simply
renders no extra section (the page is still valid, just shorter). Fill in the
remaining tools over time; keep every claim factually true to what the tool
actually does — inaccurate copy hurts both users and rankings.

Format: EXTRA[slug] is a block of server-rendered HTML using <h2>/<h3>/<p>/<ul>.
Keep internal links to sibling tools (they strengthen internal linking) and to
the matching /blog guide where one exists.
"""
from typing import Dict

EXTRA: Dict[str, str] = {
    # ---- PDF: high-traffic ------------------------------------------------
    "merge-pdf": """
        <h2>What you can merge</h2>
        <p>Combine any number of PDF files into a single document — reports and
            their appendices, scanned pages, invoices, or chapters exported
            separately. There is no two-file free cap and no page limit beyond your
            upload size. Drag the files into the order you want before merging, so
            the final PDF reads top-to-bottom exactly as intended.</p>
        <h2>Common uses</h2>
        <ul>
            <li>Bundling a cover letter, CV, and portfolio into one file to upload.</li>
            <li>Joining separately scanned pages back into one document.</li>
            <li>Combining monthly statements or invoices for a single submission.</li>
        </ul>
        <h2>Merge vs. split, organize, and compress</h2>
        <p>Merging only joins files. If you also need to drop or reorder pages,
            <a href="/organize-pdf">Organize PDF</a> gives you page-level control; to
            pull pages out instead, use <a href="/split-pdf">Split PDF</a>. Merged a
            lot of image-heavy files? Run the result through
            <a href="/compress-pdf">Compress PDF</a> once at the end to keep the size
            down.</p>""",

    "compress-pdf": """
        <h2>How compression works here</h2>
        <p>Compress PDF re-samples oversized embedded images and strips redundant
            data while keeping text as sharp vector glyphs, so words never blur. Most
            savings come from images and scans; a text-only PDF is already small.
            Pick a level to trade size against image fidelity — screen-resolution
            output is ideal for email and web uploads, while you should keep the
            original for high-DPI commercial printing.</p>
        <h2>When you need it</h2>
        <ul>
            <li>A PDF is too big to attach to an email or upload to a portal.</li>
            <li>A scanned document is huge because it's really a stack of images.</li>
            <li>You merged several files and the combined PDF ballooned in size.</li>
        </ul>
        <p>For the full walkthrough and the quality trade-offs, see our guide:
            <a href="/blog/how-to-compress-a-pdf-without-losing-quality">how to compress
            a PDF without losing quality</a>.</p>""",

    "pdf-to-word": """
        <h2>What converts well</h2>
        <p>PDF to Word rebuilds paragraphs, headings, and simple tables into a real
            editable <code>.docx</code> — not an image pasted into a page — so you can
            open and edit it in Microsoft Word, Google Docs, or LibreOffice. Digital
            PDFs (exported from Word, a browser, or design software) convert cleanly;
            very complex multi-column layouts may need light clean-up afterwards, which
            is normal for any PDF-to-Word conversion.</p>
        <h2>Scanned PDFs</h2>
        <p>If your PDF is a scan or photo, the "text" is really an image. It's run
            through OCR (optical character recognition), which runs fully offline on our
            server, so the recognised words come back editable rather than locked in a
            picture.</p>
        <h2>Locked PDFs</h2>
        <p>Password-protected PDFs must be opened first —
            <a href="/unlock-pdf">remove the password</a> (on a file you own), then
            convert. Both tools are free. Full walkthrough:
            <a href="/blog/how-to-convert-pdf-to-word-for-free">how to convert a PDF to
            Word for free</a>.</p>""",

    "unlock-pdf": """
        <h2>What "unlock" means</h2>
        <p>Unlock PDF removes the open/permissions password from a PDF <strong>you
            own</strong> so you can view, copy, print, or convert it freely. Use it on
            your own bank statements, payslips, or documents whose password you know —
            not on files you aren't authorised to open.</p>
        <h2>After unlocking</h2>
        <ul>
            <li>Convert it: <a href="/pdf-to-word">PDF to Word</a>,
                <a href="/pdf-to-jpg">PDF to JPG</a>, or
                <a href="/pdf-to-excel">PDF to Excel</a>.</li>
            <li>Edit its pages with <a href="/organize-pdf">Organize PDF</a> or
                <a href="/split-pdf">Split PDF</a>.</li>
            <li>Re-secure it later with a new password using
                <a href="/protect-pdf">Protect PDF</a>.</li>
        </ul>
        <h2>Is it private?</h2>
        <p>Your file and its password never leave the processing step — the upload is
            deleted right after download, and because the code is open source you can
            verify exactly how the password is handled.</p>""",

    "split-pdf": """
        <h2>Ways to split</h2>
        <p>Pull out exactly the pages you need: a single page, a range like
            <code>5-10</code>, or a mix such as <code>1,3,5-10</code>. The selected
            pages come out as a new PDF, leaving your original untouched. It's the fast
            way to extract a chapter, remove confidential pages before sharing, or grab
            one page out of a long document.</p>
        <h2>Split, extract, or organize?</h2>
        <ul>
            <li><a href="/split-pdf">Split PDF</a> — carve out pages/ranges into a new file.</li>
            <li><a href="/extract-pdf-pages">Extract PDF pages</a> — pick specific pages to keep.</li>
            <li><a href="/organize-pdf">Organize PDF</a> — reorder, rotate, and delete pages visually.</li>
        </ul>
        <p>Need the opposite? <a href="/merge-pdf">Merge PDF</a> joins files back
            together.</p>""",

    "pdf-to-jpg": """
        <h2>PDF pages to images</h2>
        <p>PDF to JPG renders each page as a standalone JPEG image — handy when you need
            a preview thumbnail, want to drop a page into a slide or social post, or
            need to share a page with someone who can't open PDFs. Every page becomes
            its own image so you can use just the ones you want.</p>
        <h2>Related conversions</h2>
        <ul>
            <li>Going the other way? <a href="/image-to-pdf">Image to PDF</a> turns
                photos or scans into a single PDF.</li>
            <li>Need the words, not a picture? <a href="/pdf-to-text">PDF to text</a>
                or <a href="/pdf-to-word">PDF to Word</a> keep text editable.</li>
        </ul>""",

    # ---- Image: high-traffic ---------------------------------------------
    "heic-to-jpeg": """
        <h2>Why iPhone photos need converting</h2>
        <p>Modern iPhones save photos as HEIC, which stores the same quality at about
            half the size of JPG — great for your phone, but many Windows apps, older
            devices, web upload forms, and messaging tools still don't support it, so
            the photo looks broken or won't upload. Converting to JPG produces a file
            that opens everywhere.</p>
        <h2>Tips</h2>
        <ul>
            <li>Want your iPhone to shoot JPG from now on? <strong>Settings → Camera →
                Formats → Most Compatible.</strong> Existing HEIC files still need
                converting.</li>
            <li>Turning photos into a document instead? Convert to JPG, then combine
                them with <a href="/image-to-pdf">Image to PDF</a>.</li>
        </ul>
        <p>Full walkthrough:
            <a href="/blog/how-to-convert-heic-to-jpg">how to convert HEIC to JPG</a>.</p>""",

    "image-to-pdf": """
        <h2>Turn photos and scans into one PDF</h2>
        <p>Image to PDF combines JPG, PNG, and other images into a single PDF in the
            order you choose — ideal for receipts, ID documents, handwritten notes, or a
            set of scanned pages that should travel as one file. Reorder the images
            before converting so the pages come out in the right sequence.</p>
        <h2>Good to know</h2>
        <ul>
            <li>iPhone photos are HEIC — convert them first with
                <a href="/heic-to-jpeg">HEIC to JPG</a>, then build your PDF.</li>
            <li>Big photos make big PDFs; run the result through
                <a href="/compress-pdf">Compress PDF</a> if you need a smaller file.</li>
            <li>Need images out of a PDF instead? Use <a href="/pdf-to-jpg">PDF to JPG</a>.</li>
        </ul>""",
}


def extra_html(slug: str) -> str:
    """Return the tool-specific extended-content block for ``slug``, or '' if
    none is defined yet (the page then renders without it)."""
    return EXTRA.get(slug, "")
