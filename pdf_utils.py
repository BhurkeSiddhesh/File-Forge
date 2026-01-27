import pikepdf
from pathlib import Path
from pdf2docx import Converter
import os

def remove_pdf_password(input_path: str, password: str, output_dir: str) -> str:
    """Removes password from PDF and saves to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_unlocked.pdf"
    
    with pikepdf.open(input_file, password=password) as pdf:
        pdf.save(output_file)
    
    return str(output_file)

def pdf_to_docx(input_path: str, output_dir: str) -> str:
    """Converts PDF to DOCX and saves to output_dir."""
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}.docx"
    
    cv = Converter(str(input_file))
    cv.convert(str(output_file))
    cv.close()
    
    return str(output_file)
