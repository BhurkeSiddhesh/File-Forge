import os
import shutil
import warnings
from pathlib import Path

# Suppress warnings for clean output
warnings.filterwarnings("ignore")

from scripts.image_utils import (
    heic_to_jpeg, resize_image, crop_image, rotate_image,
    compress_image, convert_image_format, watermark_image
)
from scripts.pdf_utils import (
    remove_pdf_password, protect_pdf, images_to_pdf, word_to_pdf,
    pdf_to_excel, pdf_to_pptx, extract_text_from_pdf, organize_pdf,
    add_page_numbers, repair_pdf, annotate_pdf, edit_pdf_metadata
)
from scripts.excel_utils import (
    excel_to_pdf, csv_to_xlsx, xlsx_to_csv, merge_excel_files
)
from scripts.ppt_utils import (
    ppt_to_pdf, ppt_to_images_zip, merge_pptx
)
from PIL import Image
import pillow_heif

def main():
    print("--- Setting up directories ---")
    asset_dir = Path("asset")
    out_dir = Path("asset_outputs")
    if out_dir.exists():
        shutil.rmtree(out_dir)
    out_dir.mkdir(parents=True)

    # Assets
    img_jpg = asset_dir / "IMG_1939.jpg"
    pdf_1 = asset_dir / "Impact_Driven_Data_Consulting.pdf"
    pdf_2 = asset_dir / "Siddhesh_Bhurke_Resume_test.pdf"
    excel_file = asset_dir / "tradebook-EQ.xlsx"

    print("--- 1. Preprocessing (creating HEIC and Password-Protected PDF) ---")
    # Convert JPG to HEIC
    heic_path = out_dir / "IMG_1939.heic"
    try:
        pillow_heif.register_heif_opener()
        with Image.open(img_jpg) as img:
            # pillow_heif supports saving as HEIF
            img.save(heic_path, format="HEIF")
        print(f"Created HEIC image: {heic_path}")
    except Exception as e:
        print(f"Error creating HEIC (skipping HEIC tests): {e}")
        heic_path = None

    # Add password to PDF
    try:
        protected_pdf = protect_pdf(str(pdf_2), str(out_dir), user_password="password123")
        print(f"Created password-protected PDF: {protected_pdf}")
    except Exception as e:
        print(f"Error protecting PDF: {e}")
        protected_pdf = None


    print("\n--- 2. Image Features ---")
    try:
        if heic_path and heic_path.exists():
            res = heic_to_jpeg(str(heic_path), str(out_dir))
            print(f"[heic_to_jpeg] Output: {res}")
        
        res = resize_image(str(img_jpg), str(out_dir), mode="dimensions", width=500, height=500)
        print(f"[resize_image (dimensions)] Output: {res}")
        
        res = resize_image(str(img_jpg), str(out_dir), mode="percentage", percentage=50)
        print(f"[resize_image (percentage)] Output: {res}")

        res = resize_image(str(img_jpg), str(out_dir), mode="target_size", target_size_kb=50)
        print(f"[resize_image (target_size)] Output: {res}")

        res = crop_image(str(img_jpg), str(out_dir), x=10, y=10, width=100, height=100)
        print(f"[crop_image] Output: {res}")

        res = rotate_image(str(img_jpg), str(out_dir), angle=90)
        print(f"[rotate_image] Output: {res}")

        res = compress_image(str(img_jpg), str(out_dir), quality=50)
        print(f"[compress_image] Output: {res['output_path']} (Reduction: {res['reduction_pct']}%)")

        res = convert_image_format(str(img_jpg), str(out_dir), target_format="webp")
        print(f"[convert_image_format] Output: {res}")

        res = watermark_image(str(img_jpg), str(out_dir), text="CONFIDENTIAL", position="center")
        print(f"[watermark_image] Output: {res}")
    except Exception as e:
        print(f"Error in Image Features: {e}")

    print("\n--- 3. Excel Features ---")
    generated_csv = None
    try:
        res = excel_to_pdf(str(excel_file), str(out_dir))
        print(f"[excel_to_pdf] Output: {res}")

        res = xlsx_to_csv(str(excel_file), str(out_dir))
        generated_csv = res
        print(f"[xlsx_to_csv] Output: {res}")

        if generated_csv:
            res_xlsx = csv_to_xlsx(generated_csv, str(out_dir))
            print(f"[csv_to_xlsx] Output: {res_xlsx}")

            res = merge_excel_files([str(excel_file), res_xlsx], str(out_dir))
            print(f"[merge_excel_files] Output: {res}")
    except Exception as e:
        print(f"Error in Excel Features: {e}")

    print("\n--- 4. PDF Features ---")
    generated_pptx = None
    try:
        if protected_pdf:
            res = remove_pdf_password(str(protected_pdf), "password123", str(out_dir))
            print(f"[remove_pdf_password] Output: {res}")

        res = images_to_pdf([str(img_jpg)], str(out_dir))
        print(f"[images_to_pdf] Output: {res}")

        res = pdf_to_excel(str(pdf_1), str(out_dir))
        print(f"[pdf_to_excel] Output: {res['output_path']} (Tables found: {res.get('tables_found', 0)})")

        res = pdf_to_pptx(str(pdf_1), str(out_dir))
        generated_pptx = res
        print(f"[pdf_to_pptx] Output: {res}")

        res = extract_text_from_pdf(str(pdf_2), str(out_dir))
        print(f"[extract_text_from_pdf] Output: {res['output_path']} (Pages: {res['page_count']})")

        res = organize_pdf(str(pdf_2), str(out_dir), page_order=[1])
        print(f"[organize_pdf] Output: {res}")

        res = add_page_numbers(str(pdf_2), str(out_dir))
        print(f"[add_page_numbers] Output: {res}")

        res = repair_pdf(str(pdf_1), str(out_dir))
        print(f"[repair_pdf] Output: {res['output_path']} (Status: {res['repair_status']})")

        anns = [{"type": "highlight", "page": 1, "rect": [50, 700, 300, 730], "content": "Review"}]
        res = annotate_pdf(str(pdf_2), str(out_dir), anns)
        print(f"[annotate_pdf] Output: {res}")

        res = edit_pdf_metadata(str(pdf_2), str(out_dir), title="Test Title", author="Asset Script")
        print(f"[edit_pdf_metadata] Output: {res}")
    except Exception as e:
        print(f"Error in PDF Features: {e}")

    print("\n--- 5. PPT Features ---")
    try:
        if generated_pptx:
            res = ppt_to_pdf(generated_pptx, str(out_dir))
            print(f"[ppt_to_pdf] Output: {res}")

            res = ppt_to_images_zip(generated_pptx, str(out_dir))
            print(f"[ppt_to_images_zip] Output: {res['output_path']} (Slides: {res['slide_count']})")

            # Duplicate the pptx for merging
            dup_pptx = str(out_dir / "dup.pptx")
            shutil.copy(generated_pptx, dup_pptx)
            res = merge_pptx([generated_pptx, dup_pptx], str(out_dir))
            print(f"[merge_pptx] Output: {res}")
        else:
            print("Skipping PPT features (no PPTX generated from PDF).")
    except Exception as e:
        print(f"Error in PPT Features: {e}")

    print("\n--- Feature run complete. Check the 'asset_outputs' directory for results. ---")

if __name__ == '__main__':
    main()
