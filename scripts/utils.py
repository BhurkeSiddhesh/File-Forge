"""
Common utility functions for File Forge.
Reduces code duplication across the application.
"""
import os
import shutil
import traceback
from pathlib import Path
from typing import Callable, Any
from fastapi import UploadFile, HTTPException


async def process_uploaded_file(
    file: UploadFile,
    upload_dir: Path,
    processor: Callable[[str], str],
    debug_name: str = "Processing"
) -> dict:
    """
    Common pattern for handling file upload, processing, and cleanup.
    
    Args:
        file: The uploaded file from FastAPI
        upload_dir: Directory to save temporary uploads
        processor: Function that takes temp file path and returns output path
        debug_name: Name for debug logging
    
    Returns:
        Dict with status, message, and filename
    
    Raises:
        HTTPException: If processing fails
    """
    temp_path = upload_dir / file.filename
    print(f"[DEBUG] {debug_name}: {file.filename}")
    
    try:
        # Save uploaded file
        with temp_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # Process the file
        output_path = processor(str(temp_path))
        
        print(f"[DEBUG] {debug_name} successful: {output_path}")
        return {
            "status": "success",
            "message": f"{debug_name} completed",
            "filename": Path(output_path).name
        }
    
    except Exception as e:
        print(f"[ERROR] {debug_name} failed: {e}")
        traceback.print_exc()
        raise HTTPException(status_code=400, detail=str(e))
    
    finally:
        cleanup_temp_file(temp_path)


def cleanup_temp_file(file_path: Path) -> None:
    """
    Safely remove a temporary file, handling Windows file locking issues.
    
    Args:
        file_path: Path to the file to remove
    """
    if file_path.exists():
        try:
            os.remove(file_path)
        except PermissionError:
            # Windows file locking - will be cleaned up later
            pass
