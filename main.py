from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
import shutil
import os
from pathlib import Path
from pdf_utils import remove_pdf_password, pdf_to_docx

app = FastAPI(title="File Forge API")

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
    temp_path = UPLOAD_DIR / file.filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = remove_pdf_password(str(temp_path), password, str(OUTPUT_DIR))
        return {"status": "success", "message": "Password removed", "filename": Path(output_path).name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@app.post("/api/pdf/convert-to-word")
async def api_convert_to_word(file: UploadFile = File(...)):
    temp_path = UPLOAD_DIR / file.filename
    try:
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        output_path = pdf_to_docx(str(temp_path), str(OUTPUT_DIR))
        return {"status": "success", "message": "Converted to Word", "filename": Path(output_path).name}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
    finally:
        if temp_path.exists():
            os.remove(temp_path)

@app.get("/api/download/{filename}")
async def download_file(filename: str):
    file_path = OUTPUT_DIR / filename
    if file_path.exists():
        return FileResponse(file_path, filename=filename)
    raise HTTPException(status_code=404, detail="File not found")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8001)
