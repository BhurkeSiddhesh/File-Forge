from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Depends, Security
from fastapi.security import APIKeyHeader, APIKeyQuery
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from security_utils import secure_filename
import shutil
import os
import secrets
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from pdf_utils import remove_pdf_password, pdf_to_docx, pdf_to_word_paddle
from image_utils import heic_to_jpeg

app = FastAPI(title="File Forge API")

# --- Authentication Logic ---
API_KEY_NAME = "X-API-Key"
api_key_header = APIKeyHeader(name=API_KEY_NAME, auto_error=False)
api_key_query = APIKeyQuery(name="api_key", auto_error=False)

@app.on_event("startup")
async def startup_event():
    """Warmup AI models to avoid timeout on first request."""
    print("Initializing AI Models... This may take a while on first run.")

    # Auth Setup
    api_key = os.getenv("FILE_FORGE_API_KEY")
    if not api_key:
        api_key = secrets.token_urlsafe(32)
        print("=" * 64)
        print(f"WARNING: No FILE_FORGE_API_KEY set.")
        print(f"Generated temporary API Key: {api_key}")
        print(f"Access the web UI and enter this key when prompted.")
        print("=" * 64)
    app.state.api_key = api_key

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

async def get_api_key(
    api_key_header: str = Security(api_key_header),
    api_key_query: str = Security(api_key_query)
):
    key = api_key_header or api_key_query
    if hasattr(app.state, "api_key") and key == app.state.api_key:
        return key
    raise HTTPException(status_code=403, detail="Could not validate credentials")

# Ensure directories exist
BASE_DIR = Path(__file__).parent
UPLOAD_DIR = BASE_DIR / "uploads"
OUTPUT_DIR = BASE_DIR / "outputs"

UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

@app.get("/")
async def read_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.post("/api/pdf/remove-password", dependencies=[Depends(get_api_key)])
async def api_remove_password(file: UploadFile = File(...), password: str = Form(...)):
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
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

@app.post("/api/pdf/convert-to-word", dependencies=[Depends(get_api_key)])
async def api_convert_to_word(file: UploadFile = File(...), use_ai: bool = Form(False), password: str = Form(None)):
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
    print(f"[DEBUG] Converting: {safe_name}, use_ai={use_ai}, password={'***' if password else 'None'}")
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
            output_path = pdf_to_docx(str(temp_path), str(OUTPUT_DIR), password)
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


@app.post("/api/image/heic-to-jpeg", dependencies=[Depends(get_api_key)])
async def api_heic_to_jpeg(file: UploadFile = File(...), quality: int = Form(95)):
    """Convert HEIC/HEIF image to JPEG format."""
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
    print(f"[DEBUG] Converting HEIC: {safe_name}, quality={quality}")
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


@app.post("/api/image/resize", dependencies=[Depends(get_api_key)])
async def api_resize_image(
    file: UploadFile = File(...),
    mode: str = Form(...),
    width: int = Form(None),
    height: int = Form(None),
    percentage: int = Form(None),
    target_size_kb: int = Form(None)
):
    """Resize image based on parameters."""
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
    print(f"[DEBUG] Resizing image: {safe_name}, mode={mode}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from image_utils import resize_image
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


@app.post("/api/image/crop", dependencies=[Depends(get_api_key)])
async def api_crop_image(
    file: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...)
):
    """Crop image based on coordinates."""
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
    print(f"[DEBUG] Cropping image: {safe_name}, x={x}, y={y}, w={width}, h={height}")
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        from image_utils import crop_image
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


@app.post("/api/workflow/execute", dependencies=[Depends(get_api_key)])
async def execute_workflow(file: UploadFile = File(...), steps: str = Form(...)):
    """Execute a multi-step workflow on a file with SSE progress streaming."""
    import json
    from fastapi.responses import StreamingResponse
    
    safe_name = secure_filename(file.filename)
    temp_path = UPLOAD_DIR / safe_name
    
    print(f"[DEBUG] Workflow started: {safe_name}, steps_len={len(steps)}")
    
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
                    from image_utils import resize_image
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
                    from image_utils import crop_image
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


@app.get("/api/download/{filename}", dependencies=[Depends(get_api_key)])
async def download_file(filename: str):
    safe_name = secure_filename(filename)
    file_path = OUTPUT_DIR / safe_name
    if file_path.exists():
        return FileResponse(file_path, filename=safe_name)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
