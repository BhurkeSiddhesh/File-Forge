"""Tool-specific extended content for landing pages.

WHY: every tool page shares the same short privacy note and the same
"Why use Forge Files?" benefits. To rank, each page also needs *unique*,
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
        <p>Combine any number of PDF files into a single document: reports and
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
            Pick a level to trade size against image fidelity: screen-resolution
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
            editable <code>.docx</code>, not an image pasted into a page, so you can
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
        <p>Password-protected PDFs must be opened first:
            <a href="/unlock-pdf">remove the password</a> (on a file you own), then
            convert. Both tools are free. Full walkthrough:
            <a href="/blog/how-to-convert-pdf-to-word-for-free">how to convert a PDF to
            Word for free</a>.</p>""",

    "unlock-pdf": """
        <h2>What "unlock" means</h2>
        <p>Unlock PDF removes the open/permissions password from a PDF <strong>you
            own</strong> so you can view, copy, print, or convert it freely. Use it on
            your own bank statements, payslips, or documents whose password you know,
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
        <p>Your file and its password never leave the processing step: the upload is
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
            <li><a href="/split-pdf">Split PDF</a>: carve out pages/ranges into a new file.</li>
            <li><a href="/extract-pdf-pages">Extract PDF pages</a>: pick specific pages to keep.</li>
            <li><a href="/organize-pdf">Organize PDF</a>: reorder, rotate, and delete pages visually.</li>
        </ul>
        <p>Need the opposite? <a href="/merge-pdf">Merge PDF</a> joins files back
            together.</p>""",

    "pdf-to-jpg": """
        <h2>PDF pages to images</h2>
        <p>PDF to JPG renders each page as a standalone JPEG image, handy when you need
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
            half the size of JPG, great for your phone, but many Windows apps, older
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
            order you choose, ideal for receipts, ID documents, handwritten notes, or a
            set of scanned pages that should travel as one file. Reorder the images
            before converting so the pages come out in the right sequence.</p>
        <h2>Good to know</h2>
        <ul>
            <li>iPhone photos are HEIC; convert them first with
                <a href="/heic-to-jpeg">HEIC to JPG</a>, then build your PDF.</li>
            <li>Big photos make big PDFs; run the result through
                <a href="/compress-pdf">Compress PDF</a> if you need a smaller file.</li>
            <li>Need images out of a PDF instead? Use <a href="/pdf-to-jpg">PDF to JPG</a>.</li>
        </ul>""",

    # ---- PDF: remaining ---------------------------------------------------
    "extract-pdf-pages": """
        <h2>Pull out exactly the pages you need</h2>
        <p>Type the pages you want: a single page, a range like <code>5-10</code>, or a
            mix such as <code>1,3,5-10</code>, and download them as a new PDF. Your
            original file is left untouched, so it's a safe way to keep only the pages
            that matter: one chapter, a signed page, or the exhibit from a long report.</p>
        <h2>Extract, split, or organize?</h2>
        <ul>
            <li><a href="/extract-pdf-pages">Extract PDF pages</a>: keep specific pages by number.</li>
            <li><a href="/split-pdf">Split PDF</a>: carve pages/ranges into a separate file.</li>
            <li><a href="/organize-pdf">Organize PDF</a>: reorder, rotate, and delete pages visually.</li>
        </ul>
        <p>Want the pieces back together afterwards? <a href="/merge-pdf">Merge PDF</a>
            joins files into one.</p>""",

    "pdf-to-text": """
        <h2>Get clean, plain text out of a PDF</h2>
        <p>PDF to Text extracts the words from a PDF into a simple <code>.txt</code>
            file: no formatting, no images, just the text ready to search, paste, or feed
            into another tool. It's ideal for quoting a document, copying content that a
            PDF viewer won't let you select, or preparing text for analysis.</p>
        <h2>Scanned documents</h2>
        <p>If the PDF is a scan or photo, the words are really an image. An OCR (optical
            character recognition) fallback, running fully offline on our server, reads
            the pixels and recovers the text. Need to keep layout and edit it instead of
            plain text? Use <a href="/pdf-to-word">PDF to Word</a>.</p>""",

    "rotate-pdf": """
        <h2>Fix sideways and upside-down pages for good</h2>
        <p>Scanned a document in the wrong orientation, or got a PDF where some pages are
            rotated 90°? Rotate PDF turns pages 90, 180, or 270 degrees and saves the new
            orientation into the file permanently, unlike just rotating the view in a
            reader, which resets next time someone opens it. Rotate every page at once or
            only the ones that are wrong.</p>
        <h2>Related page fixes</h2>
        <ul>
            <li>Reorder or delete pages too: <a href="/organize-pdf">Organize PDF</a>.</li>
            <li>Rotating a photo, not a PDF? Use <a href="/rotate-image">Rotate Image</a>.</li>
        </ul>""",

    "protect-pdf": """
        <h2>Encrypt a PDF with a password</h2>
        <p>Protect PDF adds a password so only the people you share it with can open the
            file, and lets you set permissions such as restricting printing or copying.
            It's the right tool before emailing a contract, a payslip, or anything
            confidential. Choose a strong password and share it separately from the file
            itself.</p>
        <h2>The opposite direction</h2>
        <p>Need to remove a password from a PDF you own (so you can edit or convert it)?
            Use <a href="/unlock-pdf">Unlock PDF</a>. You can always re-protect the file
            here afterwards. To mark a document visually as private, add a
            <a href="/watermark-pdf">CONFIDENTIAL watermark</a>.</p>""",

    "watermark-pdf": """
        <h2>Stamp text across every page</h2>
        <p>Add a text watermark (<code>DRAFT</code>, <code>CONFIDENTIAL</code>, a company
            name, or a copyright line) across every page of a PDF, with control over
            position and opacity so it's visible without hiding the content. It marks a
            document's status or ownership at a glance and discourages casual reuse.</p>
        <h2>Good pairings</h2>
        <ul>
            <li>Restrict who can open or print it: <a href="/protect-pdf">Protect PDF</a>.</li>
            <li>Add reference numbering: <a href="/pdf-page-numbers">Page numbers</a>.</li>
            <li>Watermarking an image instead? <a href="/watermark-image">Watermark Image</a>.</li>
        </ul>""",

    "pdf-page-numbers": """
        <h2>Add clear page numbering</h2>
        <p>Add page numbers to a PDF with control over position, number format
            (<code>1, 2, 3</code>, roman <code>i, ii, iii</code>, or letters
            <code>A, B, C</code>), the starting number, and which pages to skip, handy
            when a cover page or table of contents shouldn't be counted. It makes long
            reports, manuals, and bundles easy to reference and print in order.</p>
        <h2>Building a polished document</h2>
        <p>Combine with <a href="/merge-pdf">Merge PDF</a> to assemble sections first, then
            number the finished file. Add a <a href="/watermark-pdf">watermark</a> for
            status labelling.</p>""",

    "pdf-to-excel": """
        <h2>Turn PDF tables into a real spreadsheet</h2>
        <p>PDF to Excel detects tables in your PDF and rebuilds them as editable cells in
            an <code>.xlsx</code> workbook, so you can sort, total, and chart data that
            was previously locked inside a document. It's built for financial statements,
            reports, and exported data tables. Cleanly ruled tables convert best; very
            irregular layouts may need a little tidying after.</p>
        <h2>Related</h2>
        <ul>
            <li>Need the whole document editable, not just tables? <a href="/pdf-to-word">PDF to Word</a>.</li>
            <li>Just want the raw text? <a href="/pdf-to-text">PDF to text</a>.</li>
            <li>Going the other way: <a href="/excel-to-pdf">Excel to PDF</a>.</li>
        </ul>""",

    "pdf-to-powerpoint": """
        <h2>Convert a PDF into editable slides</h2>
        <p>PDF to PowerPoint turns each page of a PDF into a slide in a <code>.pptx</code>
            presentation, so you can reuse an exported deck, a one-pager, or a report as
            the starting point for a talk. Open the result in PowerPoint, Keynote, or
            Google Slides and edit from there.</p>
        <h2>Related conversions</h2>
        <ul>
            <li>Reverse it: <a href="/powerpoint-to-pdf">PowerPoint to PDF</a>.</li>
            <li>Want images of each page instead? <a href="/pdf-to-jpg">PDF to JPG</a>.</li>
        </ul>""",

    "sign-pdf": """
        <h2>Add your signature to a document</h2>
        <p>Sign PDF lets you place a signature image onto any page and position it exactly
            where it belongs (on agreements, forms, and letters) without printing,
            signing by hand, and re-scanning. Upload a transparent PNG of your signature
            for the cleanest result.</p>
        <h2>Before and after signing</h2>
        <ul>
            <li>Locked file? <a href="/unlock-pdf">Unlock PDF</a> first (on a file you own).</li>
            <li>Combine the signed page back in with <a href="/merge-pdf">Merge PDF</a>.</li>
            <li>Lock it down before sending: <a href="/protect-pdf">Protect PDF</a>.</li>
        </ul>""",

    "organize-pdf": """
        <h2>Rearrange a PDF, page by page</h2>
        <p>Organize PDF gives you visual control over a document's pages: set a new order,
            delete pages you don't need, and duplicate pages, all in one step. It's the
            tool for fixing a document whose pages are out of sequence or that contains
            pages that shouldn't be there.</p>
        <h2>How it compares</h2>
        <ul>
            <li><a href="/organize-pdf">Organize PDF</a>: reorder, delete, duplicate visually.</li>
            <li><a href="/split-pdf">Split PDF</a> / <a href="/extract-pdf-pages">Extract pages</a>: pull pages into a new file.</li>
            <li><a href="/merge-pdf">Merge PDF</a>: join separate files together.</li>
            <li><a href="/rotate-pdf">Rotate PDF</a>: fix page orientation.</li>
        </ul>""",

    # ---- Image: remaining -------------------------------------------------
    "resize-image": """
        <h2>Three ways to resize</h2>
        <p>Resize an image by exact <strong>width/height in pixels</strong>, by
            <strong>percentage</strong> to scale it up or down, or to a
            <strong>target file size in KB</strong> when a form caps the upload. That last
            mode is the one people hunt for: set "under 200 KB" and get a file that fits.
            You can also crop visually in the same tool.</p>
        <h2>Resize vs. compress vs. crop</h2>
        <ul>
            <li><a href="/resize-image">Resize</a>: change dimensions (or hit a KB target).</li>
            <li><a href="/compress-image">Compress</a>: keep dimensions, shrink file size.</li>
            <li><a href="/crop-image">Crop</a>: trim to a region of the photo.</li>
        </ul>""",

    "compress-image": """
        <h2>Shrink photos without an obvious drop in quality</h2>
        <p>Compress JPG, PNG, and WebP images with a quality slider so you control the
            balance between file size and sharpness. It's ideal for speeding up a website,
            fitting an email attachment, or getting under an upload limit. Moderate
            compression is visually indistinguishable from the original on screen.</p>
        <h2>Related</h2>
        <ul>
            <li>Need specific dimensions or a KB target? <a href="/resize-image">Resize Image</a>.</li>
            <li>Switching format (e.g. PNG → JPG for smaller size)? <a href="/convert-image">Convert Image</a>.</li>
        </ul>""",

    "convert-image": """
        <h2>Convert between JPG, PNG, and WebP</h2>
        <p>Each format has a job: <strong>JPG</strong> is smallest for photos,
            <strong>PNG</strong> keeps sharp edges and transparency for logos and
            screenshots, and <strong>WebP</strong> gives the best size for the web.
            Convert Image moves your file between them with an adjustable quality setting.</p>
        <h2>Related</h2>
        <ul>
            <li>iPhone HEIC photos won't open? <a href="/heic-to-jpeg">HEIC to JPG</a>.</li>
            <li>Just need it smaller? <a href="/compress-image">Compress Image</a>.</li>
            <li>Turning images into a document? <a href="/image-to-pdf">Image to PDF</a>.</li>
        </ul>""",

    "crop-image": """
        <h2>Trim a photo to exactly what you want</h2>
        <p>Crop Image gives you a visual drag-and-drop editor to cut away everything
            outside the part you care about: straighten a document scan, remove a
            distracting background, or frame a profile picture. It works on JPG, PNG, WebP,
            and HEIC files straight from a phone.</p>
        <h2>After cropping</h2>
        <ul>
            <li>Set exact dimensions or a file-size target: <a href="/resize-image">Resize Image</a>.</li>
            <li>Shrink the result: <a href="/compress-image">Compress Image</a>.</li>
            <li>Combine cropped scans into one file: <a href="/image-to-pdf">Image to PDF</a>.</li>
        </ul>""",

    "rotate-image": """
        <h2>Fix sideways phone photos in one click</h2>
        <p>Phone cameras often save a photo with orientation metadata that some apps
            ignore, so the picture shows up sideways or upside-down. Rotate Image turns it
            90, 180, or 270 degrees and bakes the correct orientation into the file, so it
            displays right everywhere.</p>
        <h2>Related</h2>
        <ul>
            <li>Rotating PDF pages instead? <a href="/rotate-pdf">Rotate PDF</a>.</li>
            <li>Trim it too: <a href="/crop-image">Crop Image</a>.</li>
        </ul>""",

    "watermark-image": """
        <h2>Mark your images as yours</h2>
        <p>Add a text watermark to an image (your name, brand, or a
            <code>© copyright</code> line) with control over position, colour, and
            opacity. It's the simple way to protect photos and graphics you post publicly,
            or to label a proof before sending it to a client.</p>
        <h2>Related</h2>
        <ul>
            <li>Watermarking a PDF instead? <a href="/watermark-pdf">Watermark PDF</a>.</li>
            <li>Resize or compress after: <a href="/resize-image">Resize</a> · <a href="/compress-image">Compress</a>.</li>
        </ul>""",

    # ---- Excel ------------------------------------------------------------
    "excel-to-pdf": """
        <h2>Share spreadsheets that look right everywhere</h2>
        <p>Excel to PDF renders every sheet of your XLSX or XLS workbook as a styled table
            in a PDF, so recipients see a fixed, tidy layout regardless of their software:
            no broken columns, no "which version of Excel" surprises. It's the reliable way
            to send a report, invoice, or price list for viewing and printing.</p>
        <h2>Related</h2>
        <ul>
            <li>Reverse it: <a href="/pdf-to-excel">PDF to Excel</a> pulls tables back out.</li>
            <li>Working with CSVs? <a href="/csv-to-xlsx">CSV to Excel</a> · <a href="/xlsx-to-csv">Excel to CSV</a>.</li>
        </ul>""",

    "csv-to-xlsx": """
        <h2>Turn a raw CSV into a proper workbook</h2>
        <p>CSV to Excel imports a plain CSV into a real <code>.xlsx</code> workbook so you
            get typed cells, formatting, and formula support instead of a text file. Pick
            the delimiter your file actually uses: comma, semicolon, tab, or pipe, which
            matters for exports from non-English locales where semicolons are common.</p>
        <h2>Related</h2>
        <ul>
            <li>Export back to plain text: <a href="/xlsx-to-csv">Excel to CSV</a>.</li>
            <li>Combine several workbooks: <a href="/merge-excel">Merge Excel</a>.</li>
        </ul>""",

    "xlsx-to-csv": """
        <h2>Export a sheet to universal CSV</h2>
        <p>Excel to CSV exports a chosen sheet to a plain comma-separated file, the format
            almost every database, analytics tool, and import wizard accepts. Pick which
            sheet to export when your workbook has several. CSV keeps only values (no
            formulas, styling, or multiple sheets), which is exactly what most imports
            want.</p>
        <h2>Related</h2>
        <ul>
            <li>Coming from CSV? <a href="/csv-to-xlsx">CSV to Excel</a> builds a workbook.</li>
            <li>Need a shareable, printable version? <a href="/excel-to-pdf">Excel to PDF</a>.</li>
        </ul>""",

    "merge-excel": """
        <h2>Combine multiple workbooks into one</h2>
        <p>Merge Excel joins several <code>.xlsx</code> files into a single workbook, the
            fast way to consolidate monthly sheets, per-region exports, or contributions
            from different people into one file to analyse together. No copy-pasting
            between windows.</p>
        <h2>Related</h2>
        <ul>
            <li>Standardise inputs first: <a href="/csv-to-xlsx">CSV to Excel</a>.</li>
            <li>Share the combined result: <a href="/excel-to-pdf">Excel to PDF</a>.</li>
        </ul>""",

    # ---- PowerPoint / Word ------------------------------------------------
    "powerpoint-to-pdf": """
        <h2>Send slides that open anywhere</h2>
        <p>PowerPoint to PDF converts a <code>.pptx</code> deck into a clean PDF, so anyone
            can view or print it without PowerPoint and without fonts or animations
            shifting on their machine. It's the standard way to share a finished
            presentation as a handout or for review.</p>
        <h2>Related</h2>
        <ul>
            <li>Reverse it: <a href="/pdf-to-powerpoint">PDF to PowerPoint</a>.</li>
            <li>Need each slide as an image? <a href="/ppt-to-images">PPT to Images</a>.</li>
            <li>Combine decks first: <a href="/merge-ppt">Merge PowerPoint</a>.</li>
        </ul>""",

    "ppt-to-images": """
        <h2>Every slide as a standalone image</h2>
        <p>PPT to Images exports each slide as a PNG or JPG and bundles them into a zip,
            perfect for embedding slides in a document, posting them to social media, or
            dropping a single slide into an email where a whole deck would be overkill.
            Choose PNG for crisp text and diagrams, JPG for smaller photo-heavy slides.</p>
        <h2>Related</h2>
        <ul>
            <li>Want one shareable document? <a href="/powerpoint-to-pdf">PowerPoint to PDF</a>.</li>
            <li>Combine images into a PDF: <a href="/image-to-pdf">Image to PDF</a>.</li>
        </ul>""",

    "merge-ppt": """
        <h2>Combine presentations into one deck</h2>
        <p>Merge PowerPoint joins multiple <code>.pptx</code> files into a single
            presentation, ideal for assembling a team deck from separate contributions or
            stitching modular sections into one talk. Order the files before merging so the
            slides flow correctly.</p>
        <h2>Related</h2>
        <ul>
            <li>Share the finished deck: <a href="/powerpoint-to-pdf">PowerPoint to PDF</a>.</li>
            <li>Export slides as images: <a href="/ppt-to-images">PPT to Images</a>.</li>
        </ul>""",

    "word-to-pdf": """
        <h2>Convert Word to a fixed, shareable PDF</h2>
        <p>Word to PDF converts a <code>.docx</code> document into a PDF that keeps your
            layout, fonts, and spacing exactly as designed, so it looks identical on every
            device and can't be accidentally edited. It's the expected format for
            submitting CVs, contracts, assignments, and official letters.</p>
        <h2>Related</h2>
        <ul>
            <li>Reverse it to edit again: <a href="/pdf-to-word">PDF to Word</a>.</li>
            <li>Combine with other PDFs: <a href="/merge-pdf">Merge PDF</a>.</li>
            <li>Lock it before sending: <a href="/protect-pdf">Protect PDF</a>.</li>
        </ul>""",
}


def extra_html(slug: str) -> str:
    """Return the tool-specific extended-content block for ``slug``, or '' if
    none is defined yet (the page then renders without it)."""
    return EXTRA.get(slug, "")
