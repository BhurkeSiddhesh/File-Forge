import pikepdf
from pathlib import Path
from pdf2docx import Converter
import os
import fitz
import cv2
import numpy as np
from paddleocr import PPStructure, save_structure_res
from paddleocr.ppstructure.recovery.recovery_to_doc import sorted_layout_boxes, convert_info_docx
from docxcompose.composer import Composer
from docx import Document as Document_docx
import shutil

def remove_pdf_password(input_path: str, password: str, output_dir: str) -> str:
    """Removes password from PDF and saves to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_unlocked.pdf"
    
    with pikepdf.open(input_file, password=password) as pdf:
        pdf.save(output_file)
    
    return str(output_file)

def pdf_to_docx(input_path: str, output_dir: str) -> str:
    """Converts PDF to DOCX using pdf2docx (Fast, Rule-based)."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}.docx"
    
    cv = Converter(str(input_file))
    cv.convert(str(output_file))
    cv.close()
    
    return str(output_file)

def pdf_to_word_paddle(input_path: str, output_dir: str) -> str:
    """Converts PDF to DOCX using PaddleOCR Layout Recovery (Slow, AI-based)."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_recovered.docx"

    # Create a temp directory for intermediate files
    temp_dir = Path(output_dir) / f"temp_{input_file.stem}"
    temp_dir.mkdir(exist_ok=True)

    try:
        # Initialize PaddleOCR engine
        # use_gpu=False for safety, though it handles it automatically
        table_engine = PPStructure(recovery=True, lang='en', show_log=False, use_gpu=False)

        doc = fitz.open(str(input_file))
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
            # Add a page break before appending new document?
            # docxcompose handles this, but usually appends directly.
            # PaddleOCR pages usually start with a fresh layout.
            composer.append(Document_docx(str(docx_path)))

        composer.save(str(output_file))

    finally:
        # Cleanup
        if temp_dir.exists():
            shutil.rmtree(temp_dir)

    return str(output_file)
