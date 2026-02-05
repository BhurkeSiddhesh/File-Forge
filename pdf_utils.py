import pikepdf
from pathlib import Path
from pdf2docx import Converter
import os
from utils import cleanup_temp_file

# Disable MKL-DNN/OneDNN to fix compatibility issues on Windows
# Must be set BEFORE importing paddle/paddleocr
os.environ['FLAGS_use_mkldnn'] = '0'
os.environ['MKLDNN_VERBOSE'] = '0'
os.environ['PADDLE_DISABLE_MKLDNN'] = '1'
os.environ['FLAGS_enable_mkldnn'] = '0'
# Force CPU-only mode with basic backend
os.environ['CUDA_VISIBLE_DEVICES'] = ''

import fitz
import cv2
import numpy as np
from paddleocr import PPStructure, save_structure_res
from paddleocr.ppstructure.recovery.recovery_to_doc import sorted_layout_boxes, convert_info_docx
from docxcompose.composer import Composer
from docx import Document as Document_docx
import shutil


_PADDLE_ENGINE = None

def get_paddle_engine():
    """Singleton accessor for PaddleOCR engine."""
    global _PADDLE_ENGINE
    if _PADDLE_ENGINE is None:
        print(f"[AI] Initializing PaddleOCR engine...")
        # Define explicit model paths to ensure ONNX models are found
        # These must match what fix_models.py downloaded/converted (now copied to local models dir)
        base_dir = Path(__file__).parent
        paddle_dir = base_dir / "models"
        layout_dir = paddle_dir / "layout" / "picodet_lcnet_x1_0_fgd_layout_infer"
        table_dir = paddle_dir / "table" / "en_ppstructure_mobile_v2.0_SLANet_inference"
        det_dir = paddle_dir / "det" / "en" / "en_PP-OCRv3_det_infer"
        rec_dir = paddle_dir / "rec" / "en" / "en_PP-OCRv3_rec_infer"

        # use_gpu=False for safety, enable_mkldnn=False to avoid OneDNN issues on Windows
        # usage of use_onnx=True to bypass Paddle OneDNN issues
        _PADDLE_ENGINE = PPStructure(recovery=True, lang='en', show_log=False, use_gpu=False,
                                   enable_mkldnn=False, use_onnx=True,
                                   layout_model_dir=str(layout_dir),
                                   table_model_dir=str(table_dir),
                                   det_model_dir=str(det_dir),
                                   rec_model_dir=str(rec_dir))
        print(f"[AI] PaddleOCR engine initialized")

    return _PADDLE_ENGINE


def remove_pdf_password(input_path: str, password: str, output_dir: str) -> str:
    """Removes password from PDF and saves to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_unlocked.pdf"
    
    with pikepdf.open(input_file, password=password) as pdf:
        pdf.save(output_file)
    
    return str(output_file)

def _get_decrypted_pdf_path(input_path: str, password: str = None, temp_dir: Path = None) -> tuple:
    """
    Returns (path_to_use, needs_cleanup).
    If encrypted and password provided, decrypts to temp file.
    If encrypted and no password, raises ValueError.
    If not encrypted, returns original path.
    """
    input_file = Path(input_path)
    
    # Check if PDF is encrypted
    try:
        with pikepdf.open(input_file) as pdf:
            # PDF is not encrypted or has no password
            return str(input_file), False
    except pikepdf.PasswordError:
        # PDF is encrypted
        if not password:
            raise ValueError(f"PDF is password-protected. Please provide a password.")
        
        # Decrypt to temp file
        if temp_dir is None:
            temp_dir = input_file.parent
        
        temp_file = temp_dir / f"{input_file.stem}_temp_decrypted.pdf"
        
        with pikepdf.open(input_file, password=password) as pdf:
            pdf.save(temp_file)
        
        return str(temp_file), True

def pdf_to_docx(input_path: str, output_dir: str, password: str = None) -> str:
    """Converts PDF to DOCX using pdf2docx (Fast, Rule-based)."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}.docx"
    
    # Handle encrypted PDFs
    decrypted_path, needs_cleanup = _get_decrypted_pdf_path(input_path, password)
    
    try:
        cv = Converter(decrypted_path)
        cv.convert(str(output_file))
        cv.close()
    finally:
        if needs_cleanup:
            Path(decrypted_path).unlink(missing_ok=True)
    
    return str(output_file)

def pdf_to_word_paddle(input_path: str, output_dir: str, password: str = None) -> str:
    """Converts PDF to DOCX using PaddleOCR Layout Recovery (Slow, AI-based)."""
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
        # Initialize PaddleOCR engine (Singleton)
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

        # Merge files
        master = Document_docx(str(docx_files[0]))
        composer = Composer(master)

        for docx_path in docx_files[1:]:
            # @jules: Append usually doesn't include a page break. 
            # We might want to explicitly add one if the pages are getting merged into one long stream.
            composer.append(Document_docx(str(docx_path)))

        composer.save(str(output_file))
        doc.close()

    finally:
        # Cleanup - on Windows, files might still be locked
        if temp_dir.exists():
            try:
                shutil.rmtree(temp_dir)
            except PermissionError:
                # Windows file locking - schedule for manual cleanup
                print(f"Warning: Could not fully clean up {temp_dir} - some files may be locked")
        
        # Clean up decrypted temp file if it was created
        if needs_cleanup:
            cleanup_temp_file(Path(decrypted_path))

    return str(output_file)
