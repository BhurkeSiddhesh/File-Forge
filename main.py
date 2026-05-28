from typing import List, Optional
from fastapi import FastAPI, BackgroundTasks
from fastapi import UploadFile, File, Form, HTTPException, Depends, Header, Request
from fastapi.security import APIKeyHeader
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
import uuid
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from scripts.pdf_utils import (
    remove_pdf_password,
    pdf_to_docx,
    pdf_to_word_paddle,
    extract_pdf_pages,
    compress_pdf,
    merge_pdfs,
    add_watermark,
    pdf_to_images_zip,
    sign_pdf,
    rotate_pdf,
    protect_pdf,
    images_to_pdf,
    word_to_pdf,
    pdf_to_excel,
    pdf_to_pptx,
    extract_text_from_pdf,
    organize_pdf,
    add_page_numbers,
    repair_pdf,
    create_pdf_from_text,
    create_blank_pdf,
    annotate_pdf,
    edit_pdf_metadata,
    get_pdf_metadata,
)
from scripts.image_utils import (
    heic_to_jpeg,
    rotate_image,
    compress_image,
    convert_image_format,
    watermark_image,
)
from scripts.excel_utils import (
    excel_to_pdf,
    csv_to_xlsx,
    xlsx_to_csv,
    merge_excel_files,
)
from scripts.ppt_utils import (
    ppt_to_pdf,
    ppt_to_images_zip,
    merge_pptx,
)

app = FastAPI(title="File Forge API")

@app.on_event("startup")
async def startup_event():
    """Warmup AI models to avoid timeout on first request."""
    print("Initializing AI Models... This may take a while on first run.")
    try:
        from paddleocr import PPStructure
        # Define explicit model paths to ensure ONNX models are found
        # These must match what fix_models.py downloaded/converted (now copied to local models dir)
        base_dir = Path(__file__).parent
        paddle_dir = base_dir / "models"
        layout_dir = paddle_dir / "layout" / "picodet_lcnet_x1_0_fgd_layout_infer"
        table_dir = paddle_dir / "table" / "en_ppstructure_mobile_v2.0_SLANet_inference"
        det_dir = paddle_dir / "det" / "en" / "en_PP-OCRv3_det_infer"
        rec_dir = paddle_dir / "rec" / "en" / "en_PP-OCRv3_rec_infer"

        # Initialize to trigger download/load ONNX models
        # enable_mkldnn=False and use_onnx=True for Windows compatibility
        PPStructure(recovery=True, lang='en', show_log=False, use_gpu=False, 
                    enable_mkldnn=False, use_onnx=True,
                    layout_model_dir=str(layout_dir),
                    table_model_dir=str(table_dir),
                    det_model_dir=str(det_dir),
                    rec_model_dir=str(rec_dir))

        print("AI Models initialized successfully.")
    except Exception as e:
        print(f"Warning: AI Model initialization failed: {e}")


# Ensure directories exist
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

# --- Auth Middleware ---
API_KEY_NAME = "X-API-Key"
_api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)

async def verify_api_key(
    api_key_header: str = Depends(_api_key_header),
    api_key_query: str = None,
    request=None,
):
    """Dependency that checks X-API-Key header first, then api_key query param."""
    from fastapi import Request
    return None  # placeholder — actual check done in routes via require_auth

async def require_auth(
    request: Request,
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
    api_key_query: Optional[str] = None,
):
    """Require a valid API key via X-API-Key header. Reads expected key from app.state or env var."""
    import os as _os
    expected = getattr(request.app.state, 'api_key', None) or _os.environ.get('FILE_FORGE_API_KEY')
    if not expected:
        return  # No key configured — allow all (dev mode)
    provided = api_key_header
    if not provided or provided != expected:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return provided


async def require_auth_or_query(
    request: Request,
    api_key_header: Optional[str] = Header(default=None, alias="X-API-Key"),
    api_key: Optional[str] = None,
):
    """Like require_auth but also accepts api_key as query param (for downloads)."""
    import os as _os
    expected = getattr(request.app.state, 'api_key', None) or _os.environ.get('FILE_FORGE_API_KEY')
    if not expected:
        return  # dev mode
    provided = api_key_header or api_key
    if not provided or provided != expected:
        raise HTTPException(status_code=403, detail="Could not validate credentials")
    return provided

@app.get("/")
async def read_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.post("/api/pdf/remove-password")
async def api_remove_password(
    file: UploadFile = File(...),
    password: str = Form(...),
    _auth: str = Depends(require_auth)
):
    # Sanitize filename and add UUID prefix to prevent path traversal + collisions
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = remove_pdf_password(str(temp_path), password, str(OUTPUT_DIR))
        return {"status": "success", "message": "Password removed", "filename": Path(output_path).name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass  # Windows file locking - will be cleaned up later

@app.post("/api/pdf/convert-to-word")
async def api_convert_to_word(
    file: UploadFile = File(...),
    use_ai: bool = Form(False),
    password: str = Form(None),
    _auth: str = Depends(require_auth)
):
    # Sanitize filename and add UUID prefix
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    print(f"[DEBUG] Converting: {file.filename}, use_ai={use_ai}, password={'***' if password else 'None'}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        print(f"[DEBUG] File saved to: {temp_path}")
        
        if use_ai:
            # @jules: This can be very slow for large PDFs. 
            # We should probably implement a progress bar or background task with polling.
            output_path = pdf_to_word_paddle(str(temp_path), str(OUTPUT_DIR), password)
            message = "Converted to Word with AI Layout Recovery"
        else:
            output_path = await run_in_threadpool(pdf_to_docx, str(temp_path), str(OUTPUT_DIR), password)
            message = "Converted to Word (Standard)"

        print(f"[DEBUG] Conversion successful: {output_path}")
        return {"status": "success", "message": message, "filename": Path(output_path).name}
    except Exception as e:
        import traceback
        print(f"[ERROR] Conversion failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))

    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass  # Windows file locking - will be cleaned up later

@app.post("/api/pdf/extract-pages")
async def api_extract_pages(file: UploadFile = File(...), pages: str = Form(...), password: str = Form(None)):
    temp_path = UPLOAD_DIR / file.filename
    print(f"[DEBUG] Extracting pages: {file.filename}, pages='{pages}', password={'***' if password else 'None'}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await run_in_threadpool(extract_pdf_pages, str(temp_path), str(OUTPUT_DIR), pages, password)
        return {"status": "success", "message": "Pages extracted", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Page extraction failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/compress")
async def api_compress_pdf(
    file: UploadFile = File(...),
    level: str = Form('medium'),
    password: str = Form(None),
    _auth: str = Depends(require_auth)
):
    """Compress PDF by optimizing structure and resampling large images."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    print(f"[DEBUG] Compressing: {file.filename}, level={level}, password={'***' if password else 'None'}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await run_in_threadpool(
            compress_pdf, str(temp_path), str(OUTPUT_DIR), level, password or None
        )
        return {
            "status": "success",
            "message": "PDF compressed successfully",
            "filename": Path(result['output_path']).name,
            "original_size": result['original_size'],
            "compressed_size": result['compressed_size'],
            "reduction_pct": result['reduction_pct'],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF compression failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/merge")
async def api_merge_pdfs(
    files: List[UploadFile] = File(...),
    passwords: Optional[str] = Form(None),
    _auth: str = Depends(require_auth),
):
    """Merge multiple PDFs into one. `passwords` is an optional comma-separated list aligned with files."""
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two PDF files to merge.")

    temp_paths: List[Path] = []
    try:
        for f in files:
            safe_filename = Path(f.filename.replace("\\", "/")).name
            unique_filename = f"{uuid.uuid4()}_{safe_filename}"
            temp_path = UPLOAD_DIR / unique_filename
            with temp_path.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(temp_path)

        pwd_list = None
        if passwords:
            pwd_list = [p if p else None for p in passwords.split(",")]

        output_path = await run_in_threadpool(
            merge_pdfs, [str(p) for p in temp_paths], str(OUTPUT_DIR), pwd_list
        )
        return {"status": "success", "message": "PDFs merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF merge failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in temp_paths:
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


@app.post("/api/pdf/watermark")
async def api_add_watermark(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("diagonal"),
    opacity: float = Form(0.3),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Stamp a text watermark on every page."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await run_in_threadpool(
            add_watermark, str(temp_path), str(OUTPUT_DIR), text, position, opacity, password or None
        )
        return {"status": "success", "message": "Watermark added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Watermark failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/rotate")
async def api_rotate_pdf(
    file: UploadFile = File(...),
    angle: int = Form(...),
    pages: str = Form(None),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Rotate PDF pages by specified angle (90, 180, 270 degrees)."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        output_path = await run_in_threadpool(
            rotate_pdf, str(temp_path), str(OUTPUT_DIR), angle, pages or None, password or None
        )
        return {"status": "success", "message": f"PDF rotated by {angle}°", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF rotation failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/to-images")
async def api_pdf_to_images(
    file: UploadFile = File(...),
    dpi: int = Form(150),
    fmt: str = Form("jpg"),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Render every page to an image and return a zip."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        result = await run_in_threadpool(
            pdf_to_images_zip, str(temp_path), str(OUTPUT_DIR), dpi, fmt, password or None
        )
        return {
            "status": "success",
            "message": f"Rendered {result['page_count']} page(s) to images",
            "filename": Path(result["output_path"]).name,
            "page_count": result["page_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] PDF to images failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/sign")
async def api_sign_pdf(
    file: UploadFile = File(...),
    signature: UploadFile = File(...),
    page: int = Form(1),
    x: float = Form(0.65),
    y: float = Form(0.85),
    width: float = Form(0.2),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Stamp a signature image onto the chosen page."""
    sig_ct = (signature.content_type or "").lower()
    if sig_ct not in ("image/png", "image/jpeg", "image/jpg"):
        raise HTTPException(status_code=400, detail="Signature must be a PNG or JPEG image.")

    safe_pdf = Path(file.filename.replace("\\", "/")).name
    safe_sig = Path(signature.filename.replace("\\", "/")).name
    pdf_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_pdf}"
    sig_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_sig}"
    try:
        with pdf_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        with sig_path.open("wb") as buffer:
            shutil.copyfileobj(signature.file, buffer)

        output_path = await run_in_threadpool(
            sign_pdf, str(pdf_path), str(sig_path), str(OUTPUT_DIR), page, x, y, width, password or None
        )
        return {"status": "success", "message": "Signature added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback
        print(f"[ERROR] Sign PDF failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in (pdf_path, sig_path):
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


@app.post("/api/image/heic-to-jpeg")
async def api_heic_to_jpeg(file: UploadFile = File(...), quality: int = Form(95)):
    """Convert HEIC/HEIF image to JPEG format."""
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / safe_filename
    print(f"[DEBUG] Converting HEIC: {file.filename}, quality={quality}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = heic_to_jpeg(str(temp_path), str(OUTPUT_DIR), quality)
        return {"status": "success", "message": "Converted to JPEG", "filename": Path(output_path).name}
    except Exception as e:
        import traceback
        print(f"[ERROR] HEIC conversion failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass  # Windows file locking - will be cleaned up later


@app.post("/api/image/resize")
async def api_resize_image(
    file: UploadFile = File(...),
    mode: str = Form(...),
    width: int = Form(None),
    height: int = Form(None),
    percentage: int = Form(None),
    target_size_kb: int = Form(None)
):
    """Resize image based on parameters."""
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / safe_filename
    print(f"[DEBUG] Resizing image: {file.filename}, mode={mode}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from scripts.image_utils import resize_image
        output_path = resize_image(
            str(temp_path), 
            str(OUTPUT_DIR), 
            mode,
            width=width,
            height=height,
            percentage=percentage,
            target_size_kb=target_size_kb
        )
        return {"status": "success", "message": "Image Resized", "filename": Path(output_path).name}
    except Exception as e:
        import traceback
        print(f"[ERROR] Image resize failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/image/crop")
async def api_crop_image(
    file: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...)
):
    """Crop image based on coordinates."""
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / safe_filename
    print(f"[DEBUG] Cropping image: {file.filename}, x={x}, y={y}, w={width}, h={height}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from scripts.image_utils import crop_image
        output_path = crop_image(
            str(temp_path), 
            str(OUTPUT_DIR), 
            x=x, y=y, width=width, height=height
        )
        return {"status": "success", "message": "Image Cropped", "filename": Path(output_path).name}
    except Exception as e:
        import traceback
        print(f"[ERROR] Image crop failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/image/rotate")
async def api_rotate_image(
    file: UploadFile = File(...),
    angle: float = Form(90),
    quality: int = Form(95),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(rotate_image, str(temp_path), str(OUTPUT_DIR), angle, quality)
        return {"status": "success", "message": f"Rotated by {angle}°", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/compress")
async def api_compress_image(
    file: UploadFile = File(...),
    quality: int = Form(70),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await run_in_threadpool(compress_image, str(temp_path), str(OUTPUT_DIR), quality)
        return {
            "status": "success",
            "message": "Image compressed",
            "filename": Path(result["output_path"]).name,
            "original_size": result["original_size"],
            "compressed_size": result["compressed_size"],
            "reduction_pct": result["reduction_pct"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/convert")
async def api_convert_image(
    file: UploadFile = File(...),
    target_format: str = Form(...),
    quality: int = Form(90),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(
            convert_image_format, str(temp_path), str(OUTPUT_DIR), target_format, quality
        )
        return {"status": "success", "message": f"Converted to {target_format.upper()}", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/image/watermark")
async def api_watermark_image(
    file: UploadFile = File(...),
    text: str = Form(...),
    position: str = Form("bottom-right"),
    opacity: float = Form(0.4),
    color: str = Form("white"),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(
            watermark_image, str(temp_path), str(OUTPUT_DIR), text, position, opacity, color
        )
        return {"status": "success", "message": "Watermark added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


# --- Excel Routes ---

@app.post("/api/excel/to-pdf")
async def api_excel_to_pdf(
    file: UploadFile = File(...),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(excel_to_pdf, str(temp_path), str(OUTPUT_DIR))
        return {"status": "success", "message": "Excel converted to PDF", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/csv-to-xlsx")
async def api_csv_to_xlsx(
    file: UploadFile = File(...),
    delimiter: str = Form(","),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(csv_to_xlsx, str(temp_path), str(OUTPUT_DIR), delimiter)
        return {"status": "success", "message": "CSV converted to XLSX", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/xlsx-to-csv")
async def api_xlsx_to_csv(
    file: UploadFile = File(...),
    sheet: str = Form(None),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(xlsx_to_csv, str(temp_path), str(OUTPUT_DIR), sheet or None)
        return {"status": "success", "message": "XLSX converted to CSV", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/excel/merge")
async def api_merge_excel(
    files: List[UploadFile] = File(...),
    _auth: str = Depends(require_auth),
):
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two Excel files to merge.")
    temp_paths: List[Path] = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(tp)
        output_path = await run_in_threadpool(merge_excel_files, [str(p) for p in temp_paths], str(OUTPUT_DIR))
        return {"status": "success", "message": "Excel files merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in temp_paths:
            if p.exists():
                try: os.remove(p)
                except PermissionError: pass


# --- PPT Routes ---

@app.post("/api/ppt/to-pdf")
async def api_ppt_to_pdf(
    file: UploadFile = File(...),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(ppt_to_pdf, str(temp_path), str(OUTPUT_DIR))
        return {"status": "success", "message": "PPT converted to PDF (best-effort layout)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/ppt/to-images")
async def api_ppt_to_images(
    file: UploadFile = File(...),
    fmt: str = Form("png"),
    _auth: str = Depends(require_auth),
):
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / f"{uuid.uuid4()}_{safe_filename}"
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await run_in_threadpool(ppt_to_images_zip, str(temp_path), str(OUTPUT_DIR), fmt)
        return {
            "status": "success",
            "message": f"Rendered {result['slide_count']} slide(s)",
            "filename": Path(result["output_path"]).name,
            "slide_count": result["slide_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try: os.remove(temp_path)
            except PermissionError: pass


@app.post("/api/ppt/merge")
async def api_merge_pptx(
    files: List[UploadFile] = File(...),
    _auth: str = Depends(require_auth),
):
    if not files or len(files) < 2:
        raise HTTPException(status_code=400, detail="Provide at least two PPTX files to merge.")
    temp_paths: List[Path] = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buffer:
                shutil.copyfileobj(f.file, buffer)
            temp_paths.append(tp)
        output_path = await run_in_threadpool(merge_pptx, [str(p) for p in temp_paths], str(OUTPUT_DIR))
        return {"status": "success", "message": "PPTX files merged", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in temp_paths:
            if p.exists():
                try: os.remove(p)
                except PermissionError: pass


@app.post("/api/workflow/execute")
async def execute_workflow(
    file: UploadFile = File(...),
    steps: str = Form(...),
    _auth: str = Depends(require_auth),
):
    """Execute a multi-step workflow on a file with SSE progress streaming."""
    import json
    from fastapi.responses import StreamingResponse
    
    # Sanitize filename to prevent path traversal
    safe_filename = Path(file.filename.replace("\\", "/")).name
    temp_path = UPLOAD_DIR / safe_filename
    
    print(f"[DEBUG] Workflow started: {file.filename}, steps={steps}")
    
    # Parse steps JSON
    try:
        step_list = json.loads(steps)
        if not step_list:
            raise ValueError("No steps provided")
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid steps JSON")
    
    # Save initial file
    with temp_path.open("wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    async def generate_progress():
        """Generator for SSE progress events."""
        current_file = temp_path
        
        try:
            # Process each step
            for i, step in enumerate(step_list):
                step_type = step.get('type')
                config = step.get('config', {})
                step_label = step.get('label', step_type)
                
                # Send "processing" event for this step
                yield f"data: {json.dumps({'event': 'step_start', 'step': i, 'total': len(step_list), 'label': step_label})}\n\n"
                
                print(f"[DEBUG] Step {i+1}: {step_type}")

                # Artificial delay to ensure UI updates are visible
                import asyncio
                await asyncio.sleep(1.0)
                
                if step_type == 'remove_password':
                    password = config.get('password', '')
                    if not password:
                        yield f"data: {json.dumps({'event': 'error', 'detail': 'Password required for unlock step'})}\n\n"
                        return
                    output_path = await run_in_threadpool(remove_pdf_password, str(current_file), password, str(OUTPUT_DIR))
                    current_file = Path(output_path)
                    
                elif step_type == 'pdf_to_word':
                    use_ai = config.get('use_ai', False)
                    password = config.get('password')
                    if use_ai:
                        output_path = await run_in_threadpool(pdf_to_word_paddle, str(current_file), str(OUTPUT_DIR), password)
                    else:
                        output_path = await run_in_threadpool(pdf_to_docx, str(current_file), str(OUTPUT_DIR), password)
                    current_file = Path(output_path)
                    
                elif step_type == 'heic_to_jpeg':
                    quality = config.get('quality', 95)
                    output_path = await run_in_threadpool(heic_to_jpeg, str(current_file), str(OUTPUT_DIR), quality)
                    current_file = Path(output_path)
                    
                elif step_type == 'resize_image':
                    from scripts.image_utils import resize_image
                    mode = config.get('mode', 'percentage')
                    percentage = config.get('percentage', 50)
                    output_path = await run_in_threadpool(
                        resize_image,
                        str(current_file), 
                        str(OUTPUT_DIR), 
                        mode,
                        percentage=percentage
                    )
                    current_file = Path(output_path)
                    
                elif step_type == 'crop_image':
                    from scripts.image_utils import crop_image
                    x = config.get('x', 0)
                    y = config.get('y', 0)
                    width = config.get('width', 100)
                    height = config.get('height', 100)
                    output_path = await run_in_threadpool(
                        crop_image,
                        str(current_file), 
                        str(OUTPUT_DIR), 
                        x=x, y=y, width=width, height=height
                    )
                    current_file = Path(output_path)

                elif step_type == 'compress_pdf':
                    level = config.get('level', 'medium')
                    password = config.get('password') or None
                    result = await run_in_threadpool(compress_pdf, str(current_file), str(OUTPUT_DIR), level, password)
                    current_file = Path(result['output_path'])

                elif step_type == 'rotate_image':
                    angle = config.get('angle', 90)
                    output_path = await run_in_threadpool(rotate_image, str(current_file), str(OUTPUT_DIR), angle)
                    current_file = Path(output_path)

                elif step_type == 'compress_image':
                    quality = config.get('quality', 70)
                    result = await run_in_threadpool(compress_image, str(current_file), str(OUTPUT_DIR), quality)
                    current_file = Path(result['output_path'])

                elif step_type == 'convert_image':
                    target_format = config.get('target_format', 'jpg')
                    quality = config.get('quality', 90)
                    output_path = await run_in_threadpool(
                        convert_image_format, str(current_file), str(OUTPUT_DIR), target_format, quality
                    )
                    current_file = Path(output_path)

                elif step_type == 'watermark_image':
                    text = config.get('text', 'WATERMARK')
                    position = config.get('position', 'bottom-right')
                    opacity = config.get('opacity', 0.4)
                    color = config.get('color', 'white')
                    output_path = await run_in_threadpool(
                        watermark_image, str(current_file), str(OUTPUT_DIR), text, position, opacity, color
                    )
                    current_file = Path(output_path)

                elif step_type == 'excel_to_pdf':
                    output_path = await run_in_threadpool(excel_to_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(output_path)

                elif step_type == 'csv_to_xlsx':
                    delimiter = config.get('delimiter', ',')
                    output_path = await run_in_threadpool(csv_to_xlsx, str(current_file), str(OUTPUT_DIR), delimiter)
                    current_file = Path(output_path)

                elif step_type == 'xlsx_to_csv':
                    sheet = config.get('sheet') or None
                    output_path = await run_in_threadpool(xlsx_to_csv, str(current_file), str(OUTPUT_DIR), sheet)
                    current_file = Path(output_path)

                elif step_type == 'ppt_to_pdf':
                    output_path = await run_in_threadpool(ppt_to_pdf, str(current_file), str(OUTPUT_DIR))
                    current_file = Path(output_path)

                elif step_type == 'ppt_to_images':
                    fmt = config.get('fmt', 'png')
                    result = await run_in_threadpool(ppt_to_images_zip, str(current_file), str(OUTPUT_DIR), fmt)
                    current_file = Path(result['output_path'])

                else:
                    yield f"data: {json.dumps({'event': 'error', 'detail': f'Unknown step type: {step_type}'})}\n\n"
                    return
                
                # Send "completed" event for this step
                yield f"data: {json.dumps({'event': 'step_complete', 'step': i, 'total': len(step_list), 'label': step_label})}\n\n"
            
            # Send final success event
            print(f"[DEBUG] Workflow complete: {current_file}")
            yield f"data: {json.dumps({'event': 'complete', 'message': f'Workflow completed ({len(step_list)} steps)', 'filename': current_file.name})}\n\n"
            
        except Exception as e:
            import traceback
            print(f"[ERROR] Workflow failed: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'event': 'error', 'detail': str(e)})}\n\n"
        
        finally:
            # Clean up temp file
            if temp_path.exists():
                try:
                    os.remove(temp_path)
                except PermissionError:
                    pass
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


# ─────────────────────────────────────────────────────────────
# Feature #53: Protect PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/protect")
async def api_protect_pdf(
    file: UploadFile = File(...),
    user_password: str = Form(...),
    owner_password: str = Form(None),
    allow_print: bool = Form(True),
    allow_copy: bool = Form(False),
    allow_edit: bool = Form(False),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Add password protection and permissions to a PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(
            protect_pdf, str(temp_path), str(OUTPUT_DIR),
            user_password, owner_password, allow_print, allow_copy, allow_edit, password or None
        )
        return {"status": "success", "message": "PDF protected with password", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #54: Image to PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/image/to-pdf")
async def api_images_to_pdf(
    files: List[UploadFile] = File(...),
    page_size: str = Form("A4"),
    fit_mode: str = Form("fit"),
    margin_pt: int = Form(36),
    _auth: str = Depends(require_auth),
):
    """Convert one or more images into a single PDF."""
    temp_paths = []
    try:
        for f in files:
            safe = Path(f.filename.replace("\\", "/")).name
            tp = UPLOAD_DIR / f"{uuid.uuid4()}_{safe}"
            with tp.open("wb") as buf:
                shutil.copyfileobj(f.file, buf)
            temp_paths.append(tp)

        output_path = await run_in_threadpool(
            images_to_pdf, [str(p) for p in temp_paths], str(OUTPUT_DIR), page_size, fit_mode, margin_pt
        )
        return {"status": "success", "message": f"Created PDF from {len(files)} image(s)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        for p in temp_paths:
            if p.exists():
                try:
                    os.remove(p)
                except PermissionError:
                    pass


# ─────────────────────────────────────────────────────────────
# Feature #55: Word to PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/word/to-pdf")
async def api_word_to_pdf(
    file: UploadFile = File(...),
    _auth: str = Depends(require_auth),
):
    """Convert a Word document (DOCX/DOC) to PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(word_to_pdf, str(temp_path), str(OUTPUT_DIR))
        return {"status": "success", "message": "Word document converted to PDF", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #56: PDF to Excel
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/to-excel")
async def api_pdf_to_excel(
    file: UploadFile = File(...),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Extract tables from a PDF and convert to Excel."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await run_in_threadpool(pdf_to_excel, str(temp_path), str(OUTPUT_DIR), password or None)
        return {
            "status": "success",
            "message": f"Extracted {result['tables_found']} table(s) to Excel",
            "filename": Path(result["output_path"]).name,
            "tables_found": result["tables_found"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #57: PDF to PowerPoint
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/to-pptx")
async def api_pdf_to_pptx(
    file: UploadFile = File(...),
    dpi: int = Form(150),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Convert PDF pages to a PowerPoint presentation."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(pdf_to_pptx, str(temp_path), str(OUTPUT_DIR), dpi, password or None)
        return {"status": "success", "message": "PDF converted to PowerPoint", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #58: Extract Text from PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/extract-text")
async def api_extract_text(
    file: UploadFile = File(...),
    preserve_layout: bool = Form(False),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Extract all text content from a PDF to a .txt file."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await run_in_threadpool(
            extract_text_from_pdf, str(temp_path), str(OUTPUT_DIR), preserve_layout, password or None
        )
        return {
            "status": "success",
            "message": f"Text extracted from {result['page_count']} page(s)",
            "filename": Path(result["output_path"]).name,
            "page_count": result["page_count"],
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #59: Organize PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/organize")
async def api_organize_pdf(
    file: UploadFile = File(...),
    page_order: str = Form(...),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Reorder, delete, or duplicate PDF pages. page_order is comma-separated 1-based page numbers."""
    import json as _json
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        # Parse page_order: accepts "1,3,2" or "[1,3,2]"
        raw = page_order.strip()
        if raw.startswith("["):
            order = _json.loads(raw)
        else:
            order = [int(x.strip()) for x in raw.split(",") if x.strip()]

        output_path = await run_in_threadpool(organize_pdf, str(temp_path), str(OUTPUT_DIR), order, password or None)
        return {"status": "success", "message": f"PDF organized ({len(order)} pages in output)", "filename": Path(output_path).name}
    except (ValueError, TypeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #60: Add Page Numbers
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/add-page-numbers")
async def api_add_page_numbers(
    file: UploadFile = File(...),
    position: str = Form("bottom-center"),
    start_number: int = Form(1),
    font_size: int = Form(12),
    skip_first: int = Form(0),
    fmt: str = Form("decimal"),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Insert page numbers onto each PDF page."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(
            add_page_numbers, str(temp_path), str(OUTPUT_DIR),
            position, start_number, font_size, skip_first, fmt, password or None
        )
        return {"status": "success", "message": "Page numbers added", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #61: Repair PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/repair")
async def api_repair_pdf(
    file: UploadFile = File(...),
    _auth: str = Depends(require_auth),
):
    """Attempt to recover/repair a corrupted PDF."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        result = await run_in_threadpool(repair_pdf, str(temp_path), str(OUTPUT_DIR))
        return {
            "status": "success",
            "message": f"PDF repair status: {result['repair_status']}",
            "filename": Path(result["output_path"]).name,
            "repair_status": result["repair_status"],
        }
    except RuntimeError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #62: Create PDF from Scratch
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/create-from-text")
async def api_create_pdf_from_text(
    content: str = Form(...),
    title: str = Form("Document"),
    font_size: int = Form(12),
    page_size: str = Form("A4"),
    margin_pt: int = Form(72),
    _auth: str = Depends(require_auth),
):
    """Create a new PDF from plain text content."""
    try:
        output_path = await run_in_threadpool(
            create_pdf_from_text, str(OUTPUT_DIR), content, title, font_size, page_size, margin_pt
        )
        return {"status": "success", "message": "PDF created from text", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.post("/api/pdf/create-blank")
async def api_create_blank_pdf(
    num_pages: int = Form(1),
    page_size: str = Form("A4"),
    _auth: str = Depends(require_auth),
):
    """Create a blank PDF with the given number of pages."""
    try:
        output_path = await run_in_threadpool(create_blank_pdf, str(OUTPUT_DIR), num_pages, page_size)
        return {"status": "success", "message": f"Created blank PDF with {num_pages} page(s)", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


# ─────────────────────────────────────────────────────────────
# Feature #63: Annotate / Edit PDF
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/annotate")
async def api_annotate_pdf(
    file: UploadFile = File(...),
    annotations: str = Form(...),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Add annotations (highlight/underline/strikeout/note/text/redact) to a PDF.
    annotations is a JSON array of annotation objects."""
    import json as _json
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        ann_list = _json.loads(annotations)
        if not isinstance(ann_list, list):
            raise ValueError("annotations must be a JSON array.")

        output_path = await run_in_threadpool(
            annotate_pdf, str(temp_path), str(OUTPUT_DIR), ann_list, password or None
        )
        return {"status": "success", "message": f"Added {len(ann_list)} annotation(s)", "filename": Path(output_path).name}
    except (ValueError, _json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


# ─────────────────────────────────────────────────────────────
# Feature #64: PDF Metadata Editor
# ─────────────────────────────────────────────────────────────

@app.post("/api/pdf/metadata")
async def api_edit_pdf_metadata(
    file: UploadFile = File(...),
    title: str = Form(None),
    author: str = Form(None),
    subject: str = Form(None),
    keywords: str = Form(None),
    creator: str = Form(None),
    clear_all: bool = Form(False),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Edit PDF metadata (title, author, subject, keywords, creator)."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        output_path = await run_in_threadpool(
            edit_pdf_metadata, str(temp_path), str(OUTPUT_DIR),
            title, author, subject, keywords, creator, clear_all, password or None
        )
        return {"status": "success", "message": "PDF metadata updated", "filename": Path(output_path).name}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


@app.post("/api/pdf/metadata/read")
async def api_read_pdf_metadata(
    file: UploadFile = File(...),
    password: str = Form(None),
    _auth: str = Depends(require_auth),
):
    """Read metadata from a PDF without modifying it."""
    safe_filename = Path(file.filename.replace("\\", "/")).name
    unique_filename = f"{uuid.uuid4()}_{safe_filename}"
    temp_path = UPLOAD_DIR / unique_filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        metadata = await run_in_threadpool(get_pdf_metadata, str(temp_path), password or None)
        return {"status": "success", "metadata": metadata}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            try:
                os.remove(temp_path)
            except PermissionError:
                pass


def delete_file_after_download(path: Path) -> None:
    """
    Deletes the file at the given path.
    Designed to be used as a FastAPI BackgroundTask after a file has been served.
    
    Args:
        path: Path to the file to delete.
    """
    try:
        if path.exists():
            path.unlink()
            print(f"[DEBUG] Deleted file after download: {path}")
    except OSError as e:
        print(f"[ERROR] Failed to delete file {path}: {e}")

@app.get("/api/download/{filename}")
async def download_file(filename: str, background_tasks: BackgroundTasks, _auth: str = Depends(require_auth_or_query)) -> FileResponse:
    """
    Serves a file for download from the outputs directory and schedules its deletion.
    
    Args:
        filename: The name of the file to download.
        background_tasks: FastAPI background tasks handler.
        _auth: Validated authentication key (via header or query param).
        
    Returns:
        FileResponse: The requested file.
        
    Raises:
        HTTPException: 404 if the file is not found.
    """
    # Sanitize filename to prevent path traversal
    safe_filename = Path(filename.replace("\\", "/")).name
    file_path = OUTPUT_DIR / safe_filename
    if file_path.exists():
        # Schedule the file to be deleted after the response is sent
        background_tasks.add_task(delete_file_after_download, file_path)
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", 8001))
    uvicorn.run(app, host="0.0.0.0", port=port)
