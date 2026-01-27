from pdf_utils import pdf_to_docx, pdf_to_word_paddle
import os
import shutil

# Make sure we have a file to test - use a password-protected file
INPUT_FILE = "Download Report_Aai.pdf"
PASSWORD = "3193"

if not os.path.exists(INPUT_FILE):
    # Try another one if that one is missing
    candidates = ["Download_Report_Baba.pdf", "uploads/5047ZA0380215047_337195n.pdf"]
    for c in candidates:
        if os.path.exists(c):
            INPUT_FILE = c
            break

print(f"Testing with file: {INPUT_FILE}")
OUTPUT_DIR = "test_output"

if not os.path.exists(OUTPUT_DIR):
    os.makedirs(OUTPUT_DIR)

print("--- Testing Standard Conversion (pdf2docx) with password ---")
try:
    result = pdf_to_docx(INPUT_FILE, OUTPUT_DIR, PASSWORD)
    print(f"Standard Conversion Success: {result}")
except Exception as e:
    print(f"Standard Conversion Failed: {e}")
    import traceback
    traceback.print_exc()

print("\n--- Testing AI Conversion (PaddleOCR) with password ---")
try:
    result = pdf_to_word_paddle(INPUT_FILE, OUTPUT_DIR, PASSWORD)
    print(f"AI Conversion Success: {result}")
except Exception as e:
    print(f"AI Conversion Failed: {e}")
    import traceback
    traceback.print_exc()
