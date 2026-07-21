# Forge Files — Feature Reference

Complete reference for all 36 features. New features added in this release are marked **[NEW]**.

---

## Summary

| Category | Count | Endpoints |
|---|---|---|
| PDF Tools | 21 | `/api/pdf/*` |
| Image Tools | 8 | `/api/image/*` |
| Conversion | 5 | `/api/word/*`, `/api/pdf/to-*` |
| Workflow | 1 | `/api/workflow/execute` |
| **Total** | **36** | |

---

## PDF Tools

### Unlock PDF
**Endpoint:** `POST /api/pdf/remove-password`

Remove password from an encrypted PDF.

```bash
curl -X POST http://localhost:8001/api/pdf/remove-password \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@locked.pdf" \
  -F "password=secret"
```

**Response:** `{"status": "success", "filename": "doc_unlocked.pdf"}`

---

### Convert to Word
**Endpoint:** `POST /api/pdf/convert-to-word`

Convert PDF to DOCX. Optionally use AI layout recovery.

```bash
curl -X POST http://localhost:8001/api/pdf/convert-to-word \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@document.pdf" \
  -F "use_ai=false"
```

---

### Extract Pages
**Endpoint:** `POST /api/pdf/extract-pages`

Pull selected pages into a new PDF.

```bash
curl -X POST http://localhost:8001/api/pdf/extract-pages \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@document.pdf" \
  -F "pages=1,3,5-7"
```

---

### Compress PDF
**Endpoint:** `POST /api/pdf/compress`

Reduce PDF file size. Levels: `low`, `medium`, `high`.

```bash
curl -X POST http://localhost:8001/api/pdf/compress \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@large.pdf" \
  -F "level=medium"
```

**Response includes:** `original_size`, `compressed_size`, `reduction_pct`

---

### Merge PDFs
**Endpoint:** `POST /api/pdf/merge`

Combine 2+ PDFs into one.

```bash
curl -X POST http://localhost:8001/api/pdf/merge \
  -H "X-API-Key: YOUR_KEY" \
  -F "files[]=@page1.pdf" \
  -F "files[]=@page2.pdf"
```

---

### Add Watermark
**Endpoint:** `POST /api/pdf/watermark`

Stamp text on every page. Positions: `diagonal`, `top`, `center`, `bottom`.

```bash
curl -X POST http://localhost:8001/api/pdf/watermark \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "text=CONFIDENTIAL" \
  -F "position=diagonal" \
  -F "opacity=0.3"
```

---

### PDF to Images
**Endpoint:** `POST /api/pdf/to-images`

Render every page to images (returned as ZIP).

```bash
curl -X POST http://localhost:8001/api/pdf/to-images \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "dpi=150" \
  -F "fmt=jpg"
```

---

### Sign PDF
**Endpoint:** `POST /api/pdf/sign`

Stamp a signature image onto a specified page.

```bash
curl -X POST http://localhost:8001/api/pdf/sign \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@contract.pdf" \
  -F "signature=@signature.png" \
  -F "page=1" \
  -F "x=0.65" \
  -F "y=0.85" \
  -F "width=0.2"
```

---

### OCR PDF (AI)
**Endpoint:** `POST /api/pdf/convert-to-word` (with `use_ai=true`)

AI-powered layout recovery using PaddleOCR.

---

### Rotate PDF **[NEW]**
**Endpoint:** `POST /api/pdf/rotate`

Rotate PDF pages by 90, 180, or 270 degrees. Supports per-page selection.

```bash
curl -X POST http://localhost:8001/api/pdf/rotate \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@scanned.pdf" \
  -F "angle=90" \
  -F "pages=1,3-5"
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `file` | File | required | PDF file |
| `angle` | int | required | 90, 180, 270, -90, -180, -270 |
| `pages` | string | null (all) | Page selection: `1,3-5` or `all` |
| `password` | string | null | PDF password if protected |

---

### Protect PDF **[NEW]**
**Endpoint:** `POST /api/pdf/protect`

Add password protection with configurable permissions.

```bash
curl -X POST http://localhost:8001/api/pdf/protect \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "user_password=openme" \
  -F "owner_password=editme" \
  -F "allow_print=true" \
  -F "allow_copy=false" \
  -F "allow_edit=false"
```

| Parameter | Type | Default | Description |
|---|---|---|---|
| `user_password` | string | required | Password to open the document |
| `owner_password` | string | user_password | Password granting full access |
| `allow_print` | bool | true | Allow printing |
| `allow_copy` | bool | false | Allow text copying |
| `allow_edit` | bool | false | Allow editing |

---

### Extract Text from PDF **[NEW]**
**Endpoint:** `POST /api/pdf/extract-text`

Extract all text content to a .txt file. Auto-uses OCR for scanned PDFs.

```bash
curl -X POST http://localhost:8001/api/pdf/extract-text \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@document.pdf" \
  -F "preserve_layout=false"
```

**Response includes:** `page_count`

---

### Organize PDF **[NEW]**
**Endpoint:** `POST /api/pdf/organize`

Reorder, delete, or duplicate pages using a comma-separated 1-based page list.

```bash
curl -X POST http://localhost:8001/api/pdf/organize \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "page_order=3,1,2,1"
```

| `page_order` examples | Effect |
|---|---|
| `3,1,2` | Reorder: put page 3 first |
| `1,3` | Delete page 2 |
| `1,1,2` | Duplicate page 1 |
| `[4,3,2,1]` | JSON array also accepted |

---

### Add Page Numbers **[NEW]**
**Endpoint:** `POST /api/pdf/add-page-numbers`

Insert page numbers with customizable position, format, and style.

```bash
curl -X POST http://localhost:8001/api/pdf/add-page-numbers \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "position=bottom-center" \
  -F "fmt=decimal" \
  -F "start_number=1" \
  -F "skip_first=1"
```

| Parameter | Options |
|---|---|
| `position` | `bottom-center`, `bottom-left`, `bottom-right`, `top-center`, `top-left`, `top-right` |
| `fmt` | `decimal` (1,2,3), `roman` (I,II,III), `alpha` (A,B,C) |
| `start_number` | Starting page number (default 1) |
| `skip_first` | Number of pages to skip from the start |

---

### Repair PDF **[NEW]**
**Endpoint:** `POST /api/pdf/repair`

Attempt to recover and fix a corrupted or damaged PDF.

```bash
curl -X POST http://localhost:8001/api/pdf/repair \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@corrupted.pdf"
```

**Response includes:** `repair_status` — one of `success`, `partial_recovery`, `recovered_via_mupdf`

---

### Create PDF from Text **[NEW]**
**Endpoint:** `POST /api/pdf/create-from-text`

Generate a new PDF from plain text content.

```bash
curl -X POST http://localhost:8001/api/pdf/create-from-text \
  -H "X-API-Key: YOUR_KEY" \
  -F "content=Hello World\nSecond paragraph" \
  -F "title=My Document" \
  -F "font_size=12" \
  -F "page_size=A4"
```

---

### Create Blank PDF **[NEW]**
**Endpoint:** `POST /api/pdf/create-blank`

Generate a blank PDF with a specified number of pages.

```bash
curl -X POST http://localhost:8001/api/pdf/create-blank \
  -H "X-API-Key: YOUR_KEY" \
  -F "num_pages=5" \
  -F "page_size=A4"
```

---

### Annotate PDF **[NEW]**
**Endpoint:** `POST /api/pdf/annotate`

Add highlights, underlines, strikeouts, notes, text boxes, or redactions.

```bash
curl -X POST http://localhost:8001/api/pdf/annotate \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F 'annotations=[{"type":"highlight","page":1,"rect":[50,700,300,730],"color":[1,1,0]},{"type":"note","page":1,"rect":[50,650,200,670],"content":"Review this section"}]'
```

| Annotation type | Description |
|---|---|
| `highlight` | Yellow (or custom color) highlight |
| `underline` | Underline text region |
| `strikeout` | Strike through text |
| `note` | Sticky note popup |
| `text` | Insert a text box |
| `redact` | Permanently black out content |

---

### Edit PDF Metadata **[NEW]**
**Endpoint:** `POST /api/pdf/metadata`

Update document properties: title, author, subject, keywords, creator.

```bash
curl -X POST http://localhost:8001/api/pdf/metadata \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf" \
  -F "title=Annual Report 2026" \
  -F "author=Jane Smith" \
  -F "keywords=finance,report,2026" \
  -F "clear_all=false"
```

### Read PDF Metadata **[NEW]**
**Endpoint:** `POST /api/pdf/metadata/read`

Read existing document properties without modifying the PDF.

```bash
curl -X POST http://localhost:8001/api/pdf/metadata/read \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@doc.pdf"
```

**Response:**
```json
{
  "status": "success",
  "metadata": {
    "title": "My Document",
    "author": "John Doe",
    "subject": "",
    "keywords": "pdf, tools",
    "creator": "",
    "producer": "pikepdf",
    "page_count": 5
  }
}
```

---

### PDF to Excel **[NEW]**
**Endpoint:** `POST /api/pdf/to-excel`

Extract tables from PDF pages into an Excel workbook (one sheet per table).

```bash
curl -X POST http://localhost:8001/api/pdf/to-excel \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@report.pdf"
```

**Response includes:** `tables_found`

> If no tables are detected, falls back to a text-content sheet.

---

### PDF to PowerPoint **[NEW]**
**Endpoint:** `POST /api/pdf/to-pptx`

Convert each PDF page to a PowerPoint slide (image-based).

```bash
curl -X POST http://localhost:8001/api/pdf/to-pptx \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@slides.pdf" \
  -F "dpi=150"
```

---

## Image Tools

### HEIC to JPEG
**Endpoint:** `POST /api/image/heic-to-jpeg`

### Resize Image
**Endpoint:** `POST /api/image/resize`

### Crop Image
**Endpoint:** `POST /api/image/crop`

### Rotate Image
**Endpoint:** `POST /api/image/rotate`

### Compress Image
**Endpoint:** `POST /api/image/compress`

### Convert Image Format
**Endpoint:** `POST /api/image/convert-format`

JPG ↔ PNG ↔ WebP.

### Watermark Image
**Endpoint:** `POST /api/image/watermark`

### Image to PDF **[NEW]**
**Endpoint:** `POST /api/image/to-pdf`

Convert one or more images into a multi-page PDF.

```bash
curl -X POST http://localhost:8001/api/image/to-pdf \
  -H "X-API-Key: YOUR_KEY" \
  -F "files[]=@photo1.jpg" \
  -F "files[]=@photo2.png" \
  -F "page_size=A4" \
  -F "fit_mode=fit"
```

| Parameter | Options | Description |
|---|---|---|
| `page_size` | `A4`, `Letter`, `auto` | Page size (auto = image dimensions) |
| `fit_mode` | `fit`, `original` | Scale to page or use original size |
| `margin_pt` | integer | Page margin in points (default 36) |

---

## Conversion Tools

### Excel to PDF
**Endpoint:** `POST /api/excel/to-pdf`

### PPT to PDF
**Endpoint:** `POST /api/ppt/to-pdf`

### Word to PDF **[NEW]**
**Endpoint:** `POST /api/word/to-pdf`

Convert DOCX/DOC to PDF. Uses LibreOffice if available, falls back to python-docx + reportlab.

```bash
curl -X POST http://localhost:8001/api/word/to-pdf \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@document.docx"
```

Supported formats: `.docx`, `.doc`, `.odt`, `.rtf`

---

## Spreadsheet Tools

### CSV to XLSX
**Endpoint:** `POST /api/excel/csv-to-xlsx`

### XLSX to CSV
**Endpoint:** `POST /api/excel/xlsx-to-csv`

### Merge Excel
**Endpoint:** `POST /api/excel/merge`

---

## Presentation Tools

### PPT to Images
**Endpoint:** `POST /api/ppt/to-images`

### Merge PPTX
**Endpoint:** `POST /api/ppt/merge`

---

## Workflow Builder

**Endpoint:** `POST /api/workflow/execute` (SSE streaming)

Chain multiple operations on one file with real-time progress. All new features are supported as workflow steps.

```bash
curl -X POST http://localhost:8001/api/workflow/execute \
  -H "X-API-Key: YOUR_KEY" \
  -F "file=@document.pdf" \
  -F 'steps=[
    {"type":"rotate_pdf","label":"Rotate","config":{"angle":90}},
    {"type":"add_page_numbers","label":"Number pages","config":{"position":"bottom-center"}},
    {"type":"protect_pdf","label":"Protect","config":{"user_password":"secret"}}
  ]'
```

### All supported workflow step types

| Step type | Config keys |
|---|---|
| `remove_password` | `password` |
| `pdf_to_word` | `use_ai`, `password` |
| `compress_pdf` | `level`, `password` |
| `rotate_pdf` | `angle`, `pages`, `password` |
| `protect_pdf` | `user_password`, `owner_password`, `password` |
| `word_to_pdf` | *(none)* |
| `pdf_to_excel` | `password` |
| `pdf_to_pptx` | `dpi`, `password` |
| `extract_text` | `preserve_layout`, `password` |
| `organize_pdf` | `page_order` (list), `password` |
| `add_page_numbers` | `position`, `fmt`, `start_number`, `skip_first`, `font_size`, `password` |
| `repair_pdf` | *(none)* |
| `annotate_pdf` | `annotations` (list), `password` |
| `edit_metadata` | `title`, `author`, `subject`, `keywords`, `creator`, `clear_all`, `password` |
| `watermark` | `text`, `position`, `opacity`, `password` |
| `merge_pdf` | *(not chainable — needs multiple files)* |
| `heic_to_jpeg` | `quality` |
| `rotate_image` | `angle` |
| `compress_image` | `quality` |
| `convert_image` | `target_format` |
| `watermark_image` | `text`, `position`, `opacity`, `color` |
| `excel_to_pdf` | *(none)* |
| `csv_to_xlsx` | `delimiter` |
| `xlsx_to_csv` | `sheet` |
| `ppt_to_pdf` | *(none)* |
| `ppt_to_images` | `fmt` |

---

## Authentication

All endpoints require an `X-API-Key` header when `FILE_FORGE_API_KEY` env var is set.

```bash
# Set API key in environment
export FILE_FORGE_API_KEY=your-secret-key

# Use in requests
curl -H "X-API-Key: your-secret-key" ...
```

In development (no env var set), authentication is disabled.

---

## Download

After any successful operation, download the result:

```bash
curl -O "http://localhost:8001/api/download/{filename}?api_key=YOUR_KEY"
```

Files are automatically deleted after download to save disk space.

---

## Forge Files Feature Matrix

| Feature | Input | Output | Endpoint |
|---|---|---|---|
| Remove Password | PDF | PDF | `/api/pdf/remove-password` |
| PDF → Word | PDF | DOCX | `/api/pdf/convert-to-word` |
| Extract Pages | PDF | PDF | `/api/pdf/extract-pages` |
| Compress PDF | PDF | PDF | `/api/pdf/compress` |
| Merge PDFs | PDF[] | PDF | `/api/pdf/merge` |
| Watermark PDF | PDF | PDF | `/api/pdf/watermark` |
| PDF → Images | PDF | ZIP | `/api/pdf/to-images` |
| Sign PDF | PDF + Image | PDF | `/api/pdf/sign` |
| **Rotate PDF** | PDF | PDF | `/api/pdf/rotate` |
| **Protect PDF** | PDF | PDF | `/api/pdf/protect` |
| **Extract Text** | PDF | TXT | `/api/pdf/extract-text` |
| **Organize PDF** | PDF | PDF | `/api/pdf/organize` |
| **Add Page Numbers** | PDF | PDF | `/api/pdf/add-page-numbers` |
| **Repair PDF** | PDF | PDF | `/api/pdf/repair` |
| **Create PDF (text)** | Text | PDF | `/api/pdf/create-from-text` |
| **Create PDF (blank)** | — | PDF | `/api/pdf/create-blank` |
| **Annotate PDF** | PDF | PDF | `/api/pdf/annotate` |
| **Edit Metadata** | PDF | PDF | `/api/pdf/metadata` |
| **Read Metadata** | PDF | JSON | `/api/pdf/metadata/read` |
| **PDF → Excel** | PDF | XLSX | `/api/pdf/to-excel` |
| **PDF → PowerPoint** | PDF | PPTX | `/api/pdf/to-pptx` |
| HEIC → JPEG | HEIC | JPEG | `/api/image/heic-to-jpeg` |
| Resize Image | Image | JPEG | `/api/image/resize` |
| Crop Image | Image | JPEG | `/api/image/crop` |
| Rotate Image | Image | Image | `/api/image/rotate` |
| Compress Image | Image | Image | `/api/image/compress` |
| Convert Format | Image | Image | `/api/image/convert-format` |
| Watermark Image | Image | Image | `/api/image/watermark` |
| **Image → PDF** | Image[] | PDF | `/api/image/to-pdf` |
| **Word → PDF** | DOCX | PDF | `/api/word/to-pdf` |
| Excel → PDF | XLSX | PDF | `/api/excel/to-pdf` |
| CSV → XLSX | CSV | XLSX | `/api/excel/csv-to-xlsx` |
| XLSX → CSV | XLSX | CSV | `/api/excel/xlsx-to-csv` |
| Merge Excel | XLSX[] | XLSX | `/api/excel/merge` |
| PPT → PDF | PPTX | PDF | `/api/ppt/to-pdf` |
| PPT → Images | PPTX | ZIP | `/api/ppt/to-images` |
| Merge PPTX | PPTX[] | PPTX | `/api/ppt/merge` |
| Workflow Builder | Any | Any | `/api/workflow/execute` |

**Bold** = new in this release. Total: 38 endpoints.
