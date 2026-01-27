import pikepdf
import os
from pathlib import Path

def create_benchmark_data():
    output_dir = Path("benchmark_data")
    output_dir.mkdir(exist_ok=True)

    password = "benchmark"

    print(f"Generating 10 password-protected PDFs in {output_dir}...")

    for i in range(10):
        pdf = pikepdf.new()
        pdf.add_blank_page(page_size=(595, 842)) # A4 size

        filename = output_dir / f"test_{i}.pdf"

        # Save with password protection
        pdf.save(
            filename,
            encryption=pikepdf.Encryption(
                user=password,
                owner=password,
                allow=pikepdf.Permissions(extract=False)
            )
        )
        print(f"Created {filename}")

if __name__ == "__main__":
    create_benchmark_data()
