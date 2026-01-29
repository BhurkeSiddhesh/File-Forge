"""
Image conversion utilities for File Forge.
"""
from pathlib import Path
from PIL import Image
import pillow_heif

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()


def heic_to_jpeg(input_path: str, output_dir: str, quality: int = 95) -> str:
    """
    Converts HEIC/HEIF image to JPEG format.
    
    Args:
        input_path: Path to the input HEIC/HEIF file.
        output_dir: Directory to save the converted JPEG file.
        quality: JPEG quality (1-100, default 95).
    
    Returns:
        Path to the converted JPEG file.
    """
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}.jpg"
    
    with Image.open(input_file) as img:
        # Convert RGBA or palette mode to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_file, "JPEG", quality=quality)
    
    return str(output_file)
