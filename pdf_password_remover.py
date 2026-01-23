#!/usr/bin/env python3
"""
PDF Password Remover
Removes password protection from PDF files.
"""

import argparse
import sys
from pathlib import Path

try:
    import pikepdf
except ImportError:
    print("Error: pikepdf is not installed.")
    print("Install it with: pip install pikepdf")
    sys.exit(1)


def remove_pdf_password(input_path: str, password: str, output_path: str = None) -> str:
    """
    Remove password protection from a PDF file.
    
    Args:
        input_path: Path to the password-protected PDF file
        password: The password to unlock the PDF
        output_path: Path for the output file (optional, defaults to input_unlocked.pdf)
    
    Returns:
        Path to the output file
    
    Raises:
        FileNotFoundError: If input file doesn't exist
        pikepdf.PasswordError: If password is incorrect
    """
    input_file = Path(input_path)
    
    if not input_file.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")
    
    if not input_file.suffix.lower() == '.pdf':
        raise ValueError(f"Input file must be a PDF: {input_path}")
    
    # Generate output path if not provided
    if output_path is None:
        output_file = input_file.parent / f"{input_file.stem}_unlocked.pdf"
    else:
        output_file = Path(output_path)
    
    # Open the PDF with password and save without encryption
    with pikepdf.open(input_file, password=password) as pdf:
        # Save without encryption
        pdf.save(output_file)
    
    return str(output_file)


def main():
    parser = argparse.ArgumentParser(
        description="Remove password protection from a PDF file",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python pdf_password_remover.py document.pdf mypassword
  python pdf_password_remover.py document.pdf mypassword -o unlocked.pdf
        """
    )
    
    parser.add_argument(
        "input_pdf",
        nargs='?',
        help="Path to the PDF file"
    )
    
    parser.add_argument(
        "password",
        nargs='?',
        help="Password to unlock the PDF"
    )
    
    parser.add_argument(
        "-o", "--output",
        help="Output file path (default: input_unlocked.pdf)",
        default=None
    )
    
    args = parser.parse_args()
    
    # Interactive input if positional arguments are missing
    input_pdf = args.input_pdf
    password = args.password
    
    if not input_pdf:
        input_pdf = input("Enter path to PDF file: ").strip().strip('"')
    
    if not password:
        password = input("Enter password: ").strip()

    try:
        output_path = remove_pdf_password(input_pdf, password, args.output)
        print(f"✓ Password removed successfully!")
        print(f"  Output: {output_path}")
    except FileNotFoundError as e:
        print(f"✗ Error: {e}")
        sys.exit(1)
    except pikepdf.PasswordError:
        print(f"✗ Error: Incorrect password")
        sys.exit(1)
    except Exception as e:
        print(f"✗ Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
