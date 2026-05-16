import threading
import uuid
import pikepdf
from pathlib import Path
import os
from typing import List

# Disable MKL-DNN/OneDNN to fix compatibility issues on Windows
# Must be set BEFORE importing paddle/paddleocr
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['MKLDNN_VERBOSE'] = '0'
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'
os.environ['FLAGS_enable_mkldnn'] = '0'
# Force CPU-only mode with basic backend
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import shutil


# Global cache for PaddleOCR engine to avoid expensive re-initialization
_PADDLE_ENGINE = None
_ENGINE_LOCK = threading.Lock()


def _resolve_models_dir() -> Path:
    """Resolve the Paddle models directory from common project layouts."""
    script_dir = Path(__file__).resolve().parent
    candidates = [script_dir / "models", script_dir.parent / "models"]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[1]

def get_paddle_engine():
    """Returns cached PaddleOCR engine instance, initializing if needed (thread-safe)."""
    global _PADDLE_ENGINE
    if _PADDLE_ENGINE is None:
        with _ENGINE_LOCK:
            if _PADDLE_ENGINE is None:
                print("[AI] Initializing PaddleOCR engine (first time only)...")
                try:
                    # Deferred imports to prevent boot crashes on low-resource environments
                    from paddleocr import PPStructure
                except ImportError as e:
                    print(f"[AI] Error: PaddleOCR not installed correctly. {e}")
                    raise ImportError("PaddleOCR engine is missing. If you are on the Free Tier, it might have failed to install due to size limits.")

                paddle_dir = _resolve_models_dir()
                layout_dir = paddle_dir / "layout" / "picodet_lcnet_x1_0_fgd_layout_infer"
                table_dir = paddle_dir / "table" / "en_ppstructure_mobile_v2.0_SLANet_inference"
                det_dir = paddle_dir / "det" / "en" / "en_PP-OCRv3_det_infer"
                rec_dir = paddle_dir / "rec" / "en" / "en_PP-OCRv3_rec_infer"

                try:
                    _PADDLE_ENGINE = PPStructure(
                        recovery=True, lang='en', show_log=False, use_gpu=False,
                        enable_mkldnn=False, use_onnx=True,
                        layout_model_dir=str(layout_dir),
                        table_model_dir=str(table_dir),
                        det_model_dir=str(det_dir),
                        rec_model_dir=str(rec_dir)
                    )
                except MemoryError:
                    print("[AI] CRITICAL: Out of Memory while loading PaddleOCR.")
                    raise MemoryError("Server ran out of memory loading the AI engine. Please upgrade to a 'Starter' plan on Render for this feature.")
                except Exception as e:
                    print(f"[AI] Unexpected error loading PaddleOCR: {e}")
                    raise e
                    
                print("[AI] PaddleOCR engine cached successfully")
    return _PADDLE_ENGINE

def remove_pdf_password(input_path: str, password: str, output_dir: str) -> str:
    """Removes password from PDF and saves to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_unlocked.pdf"
    
    with pikepdf.open(input_file, password=password) as pdf:
        pdf.save(output_file)
    
    return str(output_file)

def _parse_page_selection(pages: str, total_pages: int) -> List[int]:
    """Parse a page selection string (e.g., '1,3-5') into zero-based indices."""
    if pages is None:
        raise ValueError("No pages selected. Please provide page numbers or 'all'.")

    normalized = pages.strip().lower()
    if not normalized:
        raise ValueError("No pages selected. Please provide page numbers or 'all'.")

    if normalized == "all":
        return list(range(total_pages))

    indices: List[int] = []
    seen = set()

    for part in normalized.split(","):
        segment = part.strip()
        if not segment:
            continue

        if "-" in segment:
            start_str, end_str = segment.split("-", 1)
            if not start_str or not end_str:
                raise ValueError(f"Invalid page range segment: '{segment}'")
            try:
                start = int(start_str)
                end = int(end_str)
            except ValueError:
                raise ValueError(f"Invalid page range numbers: '{segment}'")
            if start < 1 or end < 1 or start > end:
                raise ValueError(f"Invalid page range segment: '{segment}'")
            for num in range(start, end + 1):
                if num not in seen:
                    seen.add(num)
                    indices.append(num - 1)
        else:
            try:
                num = int(segment)
            except ValueError:
                raise ValueError(f"Invalid page number: '{segment}'")
            if num < 1:
                raise ValueError(f"Invalid page number: '{segment}'")
            if num not in seen:
                seen.add(num)
                indices.append(num - 1)

    if not indices:
        raise ValueError("No valid pages selected.")

    if max(indices) >= total_pages:
        raise ValueError(f"Selected page number exceeds document page count ({total_pages}).")

    return indices

def _get_decrypted_pdf_path(input_path: str, password: str = None, temp_dir: Path = None) -> tuple:
    """
    Returns (path_to_use, needs_cleanup).
    If encrypted and password provided, decrypts to temp file.
    If encrypted and no password, raises ValueError.
    If not encrypted, returns original path.
    """
    input_file = Path(input_path)
    
    # Try to open PDF - check if encrypted in a single operation
    try:
        with pikepdf.open(input_file) as pdf:
            # PDF is not encrypted or has no password
            return str(input_file), False
    except pikepdf.PasswordError:
        # PDF is encrypted - need password
        if not password:
            raise ValueError(f"PDF is password-protected. Please provide a password.")
        
        # Decrypt to temp file
        if temp_dir is None:
            temp_dir = input_file.parent
        
        temp_file = temp_dir / f"{input_file.stem}_temp_decrypted.pdf"
        
        with pikepdf.open(input_file, password=password) as pdf:
            pdf.save(temp_file)
        
        return str(temp_file), True

def extract_pdf_pages(input_path: str, output_dir: str, pages: str, password: str = None) -> str:
    """Extract selected pages from PDF and save to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_extracted.pdf"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        with pikepdf.open(decrypted_path) as pdf:
            selected_indices = _parse_page_selection(pages, len(pdf.pages))

            new_pdf = pikepdf.Pdf.new()
            for idx in selected_indices:
                new_pdf.pages.append(pdf.pages[idx])

            new_pdf.save(output_file)
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)

    return str(output_file)

def compress_pdf(input_path: str, output_dir: str, level: str = 'medium', password: str = None) -> dict:
    """Compress PDF by optimizing structure and resampling large images.
    
    Returns dict with output_path, original_size, compressed_size, reduction_pct.
    """
    import io
    import fitz
    from PIL import Image as PILImage

    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_compressed.pdf"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        original_size = input_file.stat().st_size
        doc = fitz.open(decrypted_path)

        if level in ('medium', 'high'):
            max_dim = {'medium': 1200, 'high': 800}[level]
            jpeg_quality = {'medium': 72, 'high': 45}[level]

            xrefs_processed = set()
            for page in doc:
                for img_info in page.get_images(full=True):
                    xref = img_info[0]
                    if xref in xrefs_processed:
                        continue
                    xrefs_processed.add(xref)
                    try:
                        pix = fitz.Pixmap(doc, xref)

                        if pix.width <= max_dim and pix.height <= max_dim:
                            pix = None
                            continue

                        if pix.n > 3:
                            pix = fitz.Pixmap(fitz.csRGB, pix)

                        mode = "RGB" if pix.n == 3 else "RGBA"
                        pil_img = PILImage.frombytes(mode, (pix.width, pix.height), pix.samples)

                        factor = max_dim / max(pix.width, pix.height)
                        new_w = max(1, int(pix.width * factor))
                        new_h = max(1, int(pix.height * factor))
                        pil_img = pil_img.resize((new_w, new_h), PILImage.LANCZOS)

                        if pil_img.mode != 'RGB':
                            pil_img = pil_img.convert('RGB')

                        buf = io.BytesIO()
                        pil_img.save(buf, format='JPEG', quality=jpeg_quality, optimize=True)
                        jpeg_bytes = buf.getvalue()

                        doc.replace_image(xref, stream=jpeg_bytes)
                        pix = None

                    except Exception as e:
                        print(f"[COMPRESS] Skipping image xref {xref}: {e}")
                        continue

        doc.save(
            str(output_file),
            garbage=4,
            deflate=True,
            deflate_images=True,
            deflate_fonts=True,
            clean=True,
        )
        doc.close()

        compressed_size = output_file.stat().st_size
        reduction = max(0.0, (1 - compressed_size / original_size) * 100)

        return {
            'output_path': str(output_file),
            'original_size': original_size,
            'compressed_size': compressed_size,
            'reduction_pct': round(reduction, 1),
        }

    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)


def pdf_to_docx(input_path: str, output_dir: str, password: str = None) -> str:
    """Converts PDF to DOCX using pdf2docx (Fast, Rule-based)."""
    from pdf2docx import Converter

    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}.docx"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        cv = Converter(decrypted_path)
        try:
            try:
                cv.convert(str(output_file), multi_processing=True)
            except Exception:
                # Some environments (e.g. spawn-only Windows workers) can't fork — fall back.
                cv.convert(str(output_file))
        finally:
            # pdf2docx Converter holds the source PDF open via PyMuPDF until close()
            # is called. Without this finally block, a failed convert() would leak
            # the file handle and block cleanup on Windows.
            cv.close()
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)

    return str(output_file)


def merge_pdfs(input_paths: List[str], output_dir: str, passwords: List[str] = None) -> str:
    """Merge multiple PDFs into a single PDF, in the given order."""
    if not input_paths:
        raise ValueError("No input files provided for merging.")
    if len(input_paths) < 2:
        raise ValueError("Provide at least two PDF files to merge.")

    output_dir_path = Path(output_dir)
    output_file = output_dir_path / f"merged_{uuid.uuid4().hex[:8]}.pdf"

    cleanup_paths: List[str] = []
    try:
        merged = pikepdf.Pdf.new()
        for idx, path in enumerate(input_paths):
            pwd = passwords[idx] if passwords and idx < len(passwords) else None
            decrypted_path, needs_cleanup = _get_decrypted_pdf_path(path, pwd, output_dir_path)
            if needs_cleanup:
                cleanup_paths.append(decrypted_path)
            with pikepdf.open(decrypted_path) as src:
                merged.pages.extend(src.pages)
        merged.save(output_file)
    finally:
        for p in cleanup_paths:
            Path(p).unlink(missing_ok=True)

    return str(output_file)


def add_watermark(
    input_path: str,
    output_dir: str,
    text: str,
    position: str = "diagonal",
    opacity: float = 0.3,
    password: str = None,
) -> str:
    """Stamp a text watermark on every page."""
    import fitz

    if not text or not text.strip():
        raise ValueError("Watermark text cannot be empty.")
    try:
        opacity = float(opacity)
    except (TypeError, ValueError):
        raise ValueError("Opacity must be a number between 0.1 and 1.0.")
    if not 0.05 <= opacity <= 1.0:
        raise ValueError("Opacity must be between 0.1 and 1.0.")
    if position not in ("diagonal", "top", "center", "bottom"):
        raise ValueError("Position must be one of: diagonal, top, center, bottom.")

    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_watermarked.pdf"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        # Use PyMuPDF for the overlay — simpler cross-page-size handling than pikepdf overlays.
        doc = fitz.open(decrypted_path)
        try:
            for page in doc:
                rect = page.rect
                # Pick a font size relative to page width.
                font_size = max(24, int(rect.width / 12))
                color = (0.5, 0.5, 0.5)

                if position == "diagonal":
                    # Diagonal stamp anchored at page center (PyMuPDF rotate= must be a
                    # multiple of 90, so apply the 45° rotation via morph).
                    point = fitz.Point(rect.width / 2, rect.height / 2)
                    page.insert_text(
                        point,
                        text,
                        fontname="helv",
                        fontsize=font_size,
                        color=color,
                        fill_opacity=opacity,
                        morph=(point, fitz.Matrix(1, 1).prerotate(45)),
                    )
                else:
                    if position == "top":
                        y = rect.height * 0.1
                    elif position == "center":
                        y = rect.height / 2
                    else:  # bottom
                        y = rect.height * 0.9
                    # Rough horizontal centering.
                    text_width = font_size * 0.5 * len(text)
                    x = max(10, (rect.width - text_width) / 2)
                    page.insert_text(
                        fitz.Point(x, y),
                        text,
                        fontname="helv",
                        fontsize=font_size,
                        color=color,
                        fill_opacity=opacity,
                    )
            doc.save(str(output_file), garbage=3, deflate=True)
        finally:
            doc.close()
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)

    return str(output_file)


def pdf_to_images_zip(
    input_path: str,
    output_dir: str,
    dpi: int = 150,
    fmt: str = "jpg",
    password: str = None,
) -> dict:
    """Render every PDF page to an image and return a zip."""
    import zipfile
    import fitz

    try:
        dpi = int(dpi)
    except (TypeError, ValueError):
        raise ValueError("DPI must be an integer.")
    if dpi < 50 or dpi > 300:
        raise ValueError("DPI must be between 50 and 300.")

    fmt = (fmt or "jpg").lower()
    if fmt not in ("jpg", "jpeg", "png"):
        raise ValueError("Format must be jpg or png.")
    file_ext = "jpg" if fmt in ("jpg", "jpeg") else "png"

    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_pages.zip"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        doc = fitz.open(decrypted_path)
        try:
            page_count = len(doc)
            with zipfile.ZipFile(output_file, "w", compression=zipfile.ZIP_DEFLATED) as zf:
                for i, page in enumerate(doc, start=1):
                    pix = page.get_pixmap(dpi=dpi)
                    if file_ext == "jpg":
                        img_bytes = pix.tobytes("jpeg")
                    else:
                        img_bytes = pix.tobytes("png")
                    zf.writestr(f"{input_file.stem}_page_{i:03d}.{file_ext}", img_bytes)
                    pix = None
        finally:
            doc.close()
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)

    return {"output_path": str(output_file), "page_count": page_count}


def sign_pdf(
    input_path: str,
    signature_image_path: str,
    output_dir: str,
    page: int = 1,
    x: float = 0.65,
    y: float = 0.85,
    width: float = 0.2,
    password: str = None,
) -> str:
    """Stamp a signature image onto the chosen page.

    x, y, width are normalized (0-1) relative to page size. (x, y) is the top-left
    of the signature box.
    """
    import fitz

    try:
        page = int(page)
        x = float(x)
        y = float(y)
        width = float(width)
    except (TypeError, ValueError):
        raise ValueError("page must be an integer; x, y, width must be numbers.")
    if page < 1:
        raise ValueError("Page number must be >= 1.")
    if not (0.0 <= x <= 1.0 and 0.0 <= y <= 1.0):
        raise ValueError("x and y must be between 0 and 1.")
    if not (0.05 <= width <= 1.0):
        raise ValueError("width must be between 0.05 and 1.0.")
    if not Path(signature_image_path).exists():
        raise ValueError("Signature image not found.")

    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_signed.pdf"

    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)

    try:
        doc = fitz.open(decrypted_path)
        try:
            if page > len(doc):
                raise ValueError(f"Page {page} exceeds document page count ({len(doc)}).")

            target_page = doc[page - 1]
            rect = target_page.rect
            box_w = rect.width * width
            # Estimate height from image aspect ratio so the signature isn't squashed.
            try:
                from PIL import Image as PILImage
                with PILImage.open(signature_image_path) as im:
                    img_w, img_h = im.size
                aspect = img_h / img_w if img_w else 0.4
            except Exception:
                aspect = 0.4
            box_h = box_w * aspect

            x0 = rect.width * x
            y0 = rect.height * y
            x1 = min(rect.width, x0 + box_w)
            y1 = min(rect.height, y0 + box_h)
            target_rect = fitz.Rect(x0, y0, x1, y1)

            target_page.insert_image(target_rect, filename=signature_image_path, keep_proportion=True)
            doc.save(str(output_file), garbage=3, deflate=True)
        finally:
            doc.close()
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)

    return str(output_file)

def merge_docx_files(input_files: list, output_file: str) -> None:
    """Merges multiple DOCX files into one, inserting page breaks between them."""
    from docxcompose.composer import Composer
    from docx import Document as Document_docx

    if not input_files:
        raise ValueError("No input files provided for merging.")

    master = Document_docx(input_files[0])
    composer = Composer(master)

    for docx_path in input_files[1:]:
        master.add_page_break()
        composer.append(Document_docx(str(docx_path)))

    composer.save(output_file)

def pdf_to_word_paddle(input_path: str, output_dir: str, password: str = None) -> str:
    """Converts PDF to DOCX using PaddleOCR Layout Recovery (Slow, AI-based)."""
    import cv2
    import fitz
    import numpy as np

    # Deferred imports for utility functions that depend on paddleocr
    try:
        from paddleocr import save_structure_res
        from paddleocr.ppstructure.recovery.recovery_to_doc import sorted_layout_boxes, convert_info_docx
    except ImportError:
        raise ImportError("PaddleOCR sub-modules could not be loaded. Please check your installation.")

    print(f"[AI] Starting AI conversion for: {input_path}")
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_recovered.docx"

    # Create a temp directory for intermediate files
    temp_dir = Path(output_dir) / f"temp_{input_file.stem}"
    temp_dir.mkdir(exist_ok=True)
    
    # Handle encrypted PDFs
    print(f"[AI] Checking encryption...")
    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password, temp_dir)
    print(f"[AI] Using path: {decrypted_path}, needs_cleanup: {needs_cleanup}")

    try:
        # Use cached PaddleOCR engine instead of re-initializing
        table_engine = get_paddle_engine()

        doc = fitz.open(decrypted_path)
        print(f"[AI] Opened PDF with {len(doc)} pages")
        docx_files = []

        for i, page in enumerate(doc):
            # Render page to image
            # 200 DPI is a good balance between speed and quality for OCR
            pix = page.get_pixmap(dpi=200)
            img_array = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.h, pix.w, pix.n)

            # Convert to BGR if needed (PyMuPDF gives RGB)
            if pix.n == 3: # RGB
                img = cv2.cvtColor(img_array, cv2.COLOR_RGB2BGR)
            elif pix.n == 4: # RGBA
                img = cv2.cvtColor(img_array, cv2.COLOR_RGBA2BGR)
            else:
                img = cv2.cvtColor(img_array, cv2.COLOR_GRAY2BGR)

            # Run inference
            result = table_engine(img)

            # Save structure result (images, excels)
            page_name = f"page_{i}"
            save_structure_res(result, str(temp_dir), page_name)

            # Convert to DOCX using recovery module
            h, w, _ = img.shape
            res = sorted_layout_boxes(result, w)
            convert_info_docx(img, res, str(temp_dir), page_name)

            # The docx is saved as {page_name}_ocr.docx in temp_dir
            expected_docx = temp_dir / f"{page_name}_ocr.docx"

            if expected_docx.exists():
                docx_files.append(expected_docx)
            else:
                print(f"Warning: Could not find recovered docx for page {i}")

        if not docx_files:
             raise Exception("No pages were successfully converted using AI engine.")

        # Merge recovered per-page DOCX files with page breaks between them
        merge_docx_files([str(f) for f in docx_files], str(output_file))
        doc.close()

    finally:
        # Cleanup
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except Exception:
                print(f"Warning: Could not fully clean up {temp_dir}")

    return str(output_file)
