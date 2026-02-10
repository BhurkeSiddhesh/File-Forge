"""
Image conversion utilities for File Forge.
"""
from pathlib import Path
import io
from PIL import Image, ImageOps
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
        # Normalize orientation (handle EXIF tags)
        img = ImageOps.exif_transpose(img)
        
        # Convert RGBA or palette mode to RGB for JPEG compatibility
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        img.save(output_file, "JPEG", quality=quality)
    
    return str(output_file)


def resize_image(input_path: str, output_dir: str, mode: str, 
                 width: int = None, height: int = None, 
                 percentage: int = None, target_size_kb: int = None,
                 quality: int = 95) -> str:
    """
    Resizes an image based on the specified mode.

    Args:
        input_path: Path to the input image.
        output_dir: Directory to save the resized image.
        mode: 'dimensions', 'percentage', or 'target_size'.
        width: Target width (optional, for 'dimensions').
        height: Target height (optional, for 'dimensions').
        percentage: Scale percentage (optional, for 'percentage').
        target_size_kb: Target file size in KB (optional, for 'target_size').
        quality: JPEG quality.

    Returns:
        Path to the resized image.
    """
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_resized.jpg"
    
    with Image.open(input_file) as img:
        # Normalize orientation (handle EXIF tags)
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        original_width, original_height = img.size

        if mode == 'dimensions':
            if not width and not height:
                raise ValueError("Width or height must be provided for dimensions mode.")
            
            # Calculate missing dimension if only one is provided to maintain aspect ratio
            if width and not height:
                ratio = width / original_width
                new_width = width
                new_height = int(original_height * ratio)
            elif height and not width:
                ratio = height / original_height
                new_height = height
                new_width = int(original_width * ratio)
            else:
                new_width = width
                new_height = height
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img.save(output_file, "JPEG", quality=quality)

        elif mode == 'percentage':
            if not percentage:
                raise ValueError("Percentage must be provided for percentage mode.")
            
            scale = percentage / 100.0
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img.save(output_file, "JPEG", quality=quality)

        elif mode == 'target_size':
            if not target_size_kb:
                raise ValueError("Target size must be provided for target_size mode.")
            
            target_bytes = target_size_kb * 1024
            
            # Iterative approach:
            # 1. Reduce quality first (down to 60)
            # 2. Reduce dimensions if quality reduction isn't enough
            
            current_quality = 95
            buffer = io.BytesIO()
            img.save(buffer, "JPEG", quality=current_quality)

            while buffer.tell() > target_bytes:
                if current_quality > 60:
                    current_quality -= 5
                else:
                    # Quality is low, start shrinking dimensions
                    current_width, current_height = img.size
                    scale_factor = 0.9
                    new_width = int(current_width * scale_factor)
                    new_height = int(current_height * scale_factor)
                    
                    if new_width < 10 or new_height < 10:
                        break # Stop if image gets too small
                        
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)

                # Check size with new parameters
                buffer.seek(0)
                buffer.truncate()
                img.save(buffer, "JPEG", quality=current_quality)

            # Write final result to disk
            with open(output_file, "wb") as f:
                f.write(buffer.getvalue())

        else:
            raise ValueError(f"Unknown resize mode: {mode}")

    return str(output_file)


def crop_image(input_path: str, output_dir: str, 
               x: int, y: int, width: int, height: int, 
               quality: int = 95) -> str:
    """
    Crops an image based on coordinates.

    Args:
        input_path: Path to the input image.
        output_dir: Directory to save the cropped image.
        x: X coordinate of the top-left corner.
        y: Y coordinate of the top-left corner.
        width: Width of the crop box.
        height: Height of the crop box.
        quality: JPEG quality.

    Returns:
        Path to the cropped image.
    """
    input_file = Path(input_path)
    output_file = Path(output_dir) / f"{input_file.stem}_cropped.jpg"
    
    with Image.open(input_file) as img:
        # Normalize orientation (handle EXIF tags)
        img = ImageOps.exif_transpose(img)

        # Convert to RGB if needed
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
            
        # Ensure crop box is within bounds
        img_width, img_height = img.size
        x = max(0, x)
        y = max(0, y)
        right = min(img_width, x + width)
        lower = min(img_height, y + height)
        
        cropped_img = img.crop((x, y, right, lower))
        cropped_img.save(output_file, "JPEG", quality=quality)
    
    return str(output_file)

