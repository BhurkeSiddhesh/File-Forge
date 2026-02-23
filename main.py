from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
from pathlib import Path
from fastapi.concurrency import run_in_threadpool
from pdf_utils import remove_pdf_password, pdf_to_docx, pdf_to_word_paddle, get_paddle_engine
from image_utils import heic_to_jpeg
from utils import process_uploaded_file, cleanup_temp_file

app = FastAPI(title="File Forge API")

@app.on_event("startup")
async def startup_event():
    """Warmup AI models to avoid timeout on first request."""
    print("Initializing AI Models... This may take a while on first run.")
    try:
        # Initialize and cache the model via the singleton accessor
        get_paddle_engine()

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

@app.get("/")
async def read_index():
    return FileResponse(str(BASE_DIR / "static" / "index.html"))

@app.post("/api/pdf/remove-password")
async def api_remove_password(file: UploadFile = File(...), password: str = Form(...)):
    """Remove password protection from a PDF file."""
    def processor(temp_path: str) -> str:
        return remove_pdf_password(temp_path, password, str(OUTPUT_DIR))
    
    result = await process_uploaded_file(
        file, UPLOAD_DIR, processor, "Password removal"
    )
    result["message"] = "Password removed"
    return result

@app.post("/api/pdf/convert-to-word")
async def api_convert_to_word(file: UploadFile = File(...), use_ai: bool = Form(False), password: str = Form(None)):
    """Convert PDF to Word document."""
    def processor(temp_path: str) -> str:
        print(f"[DEBUG] File saved to: {temp_path}")
        if use_ai:
            # @jules: This can be very slow for large PDFs. 
            # We should probably implement a progress bar or background task with polling.
            return pdf_to_word_paddle(temp_path, str(OUTPUT_DIR), password)
        else:
            return pdf_to_docx(temp_path, str(OUTPUT_DIR), password)
    
    result = await process_uploaded_file(
        file, UPLOAD_DIR, processor, 
        f"Converting (use_ai={use_ai}, password={'***' if password else 'None'})"
    )
    result["message"] = "Converted to Word with AI Layout Recovery" if use_ai else "Converted to Word (Standard)"
    return result


@app.post("/api/image/heic-to-jpeg")
async def api_heic_to_jpeg(file: UploadFile = File(...), quality: int = Form(95)):
    """Convert HEIC/HEIF image to JPEG format."""
    def processor(temp_path: str) -> str:
        return heic_to_jpeg(temp_path, str(OUTPUT_DIR), quality)
    
    result = await process_uploaded_file(
        file, UPLOAD_DIR, processor, f"HEIC conversion (quality={quality})"
    )
    result["message"] = "Converted to JPEG"
    return result


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
    from image_utils import resize_image
    
    def processor(temp_path: str) -> str:
        return resize_image(
            temp_path, 
            str(OUTPUT_DIR), 
            mode,
            width=width,
            height=height,
            percentage=percentage,
            target_size_kb=target_size_kb
        )
    
    result = await process_uploaded_file(
        file, UPLOAD_DIR, processor, f"Image resize (mode={mode})"
    )
    result["message"] = "Image Resized"
    return result


@app.post("/api/image/crop")
async def api_crop_image(
    file: UploadFile = File(...),
    x: int = Form(...),
    y: int = Form(...),
    width: int = Form(...),
    height: int = Form(...)
):
    """Crop image based on coordinates."""
    from image_utils import crop_image
    
    def processor(temp_path: str) -> str:
        return crop_image(
            temp_path, 
            str(OUTPUT_DIR), 
            x=x, y=y, width=width, height=height
        )
    
    result = await process_uploaded_file(
        file, UPLOAD_DIR, processor, 
        f"Image crop (x={x}, y={y}, w={width}, h={height})"
    )
    result["message"] = "Image Cropped"
    return result


@app.post("/api/workflow/execute")
async def execute_workflow(file: UploadFile = File(...), steps: str = Form(...)):
    """Execute a multi-step workflow on a file with SSE progress streaming."""
    import json
    from fastapi.responses import StreamingResponse
    
    temp_path = UPLOAD_DIR / file.filename
    
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
            cleanup_temp_file(temp_path)
    
    return StreamingResponse(
        generate_progress(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
