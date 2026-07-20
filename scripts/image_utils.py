"""
Image conversion utilities for File Forge.
"""
import io
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import pillow_heif

from scripts.utils import branded_filename, original_stem

# Register HEIF opener with Pillow
pillow_heif.register_heif_opener()


def _prepare_image(img: Image.Image) -> Image.Image:
    """
    Prepare image for processing: normalize orientation and convert to RGB.
    
    Args:
        img: PIL Image object.
    
    Returns:
        Normalized and RGB-converted image.
    """
    # Normalize orientation (handle EXIF tags)
    img = ImageOps.exif_transpose(img)
    
    # Convert RGBA or palette mode to RGB for JPEG compatibility
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    
    return img


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
    output_file = Path(output_dir) / branded_filename(input_file, "jpg")
    
    with Image.open(input_file) as img:
        img = _prepare_image(img)
        img.save(output_file, "JPEG", quality=quality, optimize=True)
    
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
    output_file = Path(output_dir) / branded_filename(input_file, "jpg")
    
    with Image.open(input_file) as img:
        img = _prepare_image(img)
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
            img.save(output_file, "JPEG", quality=quality, optimize=True)

        elif mode == 'percentage':
            if not percentage:
                raise ValueError("Percentage must be provided for percentage mode.")
            
            scale = percentage / 100.0
            new_width = int(original_width * scale)
            new_height = int(original_height * scale)
            
            img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
            img.save(output_file, "JPEG", quality=quality, optimize=True)

        elif mode == 'target_size':
            if not target_size_kb:
                raise ValueError("Target size must be provided for target_size mode.")
            
            target_bytes = target_size_kb * 1024
            
            # Optimized approach using binary search for quality
            # This reduces file writes from 10+ to 3-5
            import io
            
            # First, try with optimize flag and high quality
            img.save(output_file, "JPEG", quality=95, optimize=True)
            current_size = output_file.stat().st_size
            
            if current_size <= target_bytes:
                # Already under target with high quality
                return str(output_file)
            
            # Binary search for optimal quality (between 30 and 95)
            min_quality = 30
            max_quality = 95
            best_quality = min_quality
            
            while min_quality <= max_quality:
                mid_quality = (min_quality + max_quality) // 2
                
                # Test quality in memory first (faster than disk I/O)
                buffer = io.BytesIO()
                img.save(buffer, "JPEG", quality=mid_quality, optimize=True)
                test_size = buffer.tell()
                
                if test_size <= target_bytes:
                    # This quality works, try higher
                    best_quality = mid_quality
                    min_quality = mid_quality + 1
                else:
                    # Too large, try lower quality
                    max_quality = mid_quality - 1
            
            # Save with best quality found
            img.save(output_file, "JPEG", quality=best_quality, optimize=True)
            
            # If still too large, progressively resize dimensions
            if output_file.stat().st_size > target_bytes:
                scale_factor = 0.9
                while output_file.stat().st_size > target_bytes:
                    current_width, current_height = img.size
                    new_width = int(current_width * scale_factor)
                    new_height = int(current_height * scale_factor)
                    
                    if new_width < 10 or new_height < 10:
                        break  # Stop if image gets too small
                    
                    img = img.resize((new_width, new_height), Image.Resampling.LANCZOS)
                    img.save(output_file, "JPEG", quality=best_quality, optimize=True)

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
    output_file = Path(output_dir) / branded_filename(input_file, "jpg")
    
    with Image.open(input_file) as img:
        img = _prepare_image(img)
            
        # Ensure crop box is within bounds
        img_width, img_height = img.size
        x = max(0, x)
        y = max(0, y)
        right = min(img_width, x + width)
        lower = min(img_height, y + height)
        
        cropped_img = img.crop((x, y, right, lower))
        cropped_img.save(output_file, "JPEG", quality=quality, optimize=True)

    return str(output_file)


_FORMAT_EXT = {"jpg": "jpg", "jpeg": "jpg", "png": "png", "webp": "webp"}
_FORMAT_PIL = {"jpg": "JPEG", "jpeg": "JPEG", "png": "PNG", "webp": "WEBP"}


def _save_pil(img: Image.Image, output_file: Path, fmt: str, quality: int = 90) -> None:
    """Save a PIL image in the chosen format with sane defaults."""
    pil_fmt = _FORMAT_PIL[fmt]
    if pil_fmt == "JPEG":
        if img.mode != "RGB":
            img = img.convert("RGB")
        img.save(output_file, pil_fmt, quality=quality, optimize=True)
    elif pil_fmt == "PNG":
        img.save(output_file, pil_fmt, optimize=True)
    else:  # WEBP
        img.save(output_file, pil_fmt, quality=quality, method=6)


def rotate_image(input_path: str, output_dir: str, angle: float, quality: int = 95) -> str:
    """Rotate an image counter-clockwise by `angle` degrees (90/180/270 are lossless-friendly)."""
    try:
        angle = float(angle)
    except (TypeError, ValueError):
        raise ValueError("angle must be a number.")

    input_file = Path(input_path)
    fmt = (input_file.suffix.lower().lstrip(".") or "jpg")
    if fmt not in _FORMAT_EXT:
        fmt = "jpg"
    output_file = Path(output_dir) / branded_filename(input_file, _FORMAT_EXT[fmt])

    with Image.open(input_file) as img:
        img = ImageOps.exif_transpose(img)
        # expand=True so rotated bounds are not clipped.
        rotated = img.rotate(angle, resample=Image.Resampling.BICUBIC, expand=True)
        _save_pil(rotated, output_file, fmt, quality=quality)

    return str(output_file)


def compress_image(input_path: str, output_dir: str, quality: int = 70) -> dict:
    """Re-encode an image at a lower quality (JPEG/WebP) or with optimize=True (PNG)."""
    try:
        quality = int(quality)
    except (TypeError, ValueError):
        raise ValueError("quality must be an integer.")
    if not 1 <= quality <= 100:
        raise ValueError("quality must be between 1 and 100.")

    input_file = Path(input_path)
    fmt = input_file.suffix.lower().lstrip(".")
    if fmt not in _FORMAT_EXT:
        fmt = "jpg"
    output_file = Path(output_dir) / branded_filename(input_file, _FORMAT_EXT[fmt])

    original_size = input_file.stat().st_size
    with Image.open(input_file) as img:
        img = ImageOps.exif_transpose(img)
        _save_pil(img, output_file, fmt, quality=quality)

    compressed_size = output_file.stat().st_size
    reduction = max(0.0, (1 - compressed_size / original_size) * 100) if original_size else 0.0
    return {
        "output_path": str(output_file),
        "original_size": original_size,
        "compressed_size": compressed_size,
        "reduction_pct": round(reduction, 1),
    }


def convert_image_format(input_path: str, output_dir: str, target_format: str, quality: int = 90) -> str:
    """Convert an image to JPG/PNG/WebP."""
    target_format = (target_format or "").lower()
    if target_format not in _FORMAT_EXT:
        raise ValueError("target_format must be one of: jpg, png, webp.")

    input_file = Path(input_path)
    output_file = Path(output_dir) / branded_filename(input_file, _FORMAT_EXT[target_format])

    with Image.open(input_file) as img:
        img = ImageOps.exif_transpose(img)
        # PNG/WebP can keep alpha; JPEG cannot.
        if target_format in ("jpg", "jpeg") and img.mode in ("RGBA", "LA", "P"):
            img = img.convert("RGB")
        elif target_format == "png" and img.mode == "P":
            img = img.convert("RGBA")
        _save_pil(img, output_file, target_format, quality=quality)

    return str(output_file)


def watermark_image(
    input_path: str,
    output_dir: str,
    text: str,
    position: str = "bottom-right",
    opacity: float = 0.4,
    color: str = "white",
    quality: int = 95,
) -> str:
    """Stamp a text watermark on an image. position: top-left/top-right/center/bottom-left/bottom-right/diagonal."""
    if not text or not text.strip():
        raise ValueError("Watermark text cannot be empty.")
    try:
        opacity = float(opacity)
    except (TypeError, ValueError):
        raise ValueError("opacity must be a number between 0.05 and 1.0.")
    if not 0.05 <= opacity <= 1.0:
        raise ValueError("opacity must be between 0.05 and 1.0.")
    if position not in ("top-left", "top-right", "center", "bottom-left", "bottom-right", "diagonal"):
        raise ValueError("position must be one of: top-left, top-right, center, bottom-left, bottom-right, diagonal.")

    color_map = {"white": (255, 255, 255), "black": (0, 0, 0), "red": (220, 30, 30), "blue": (30, 30, 220)}
    rgb = color_map.get((color or "white").lower(), (255, 255, 255))
    alpha = int(255 * opacity)

    input_file = Path(input_path)
    fmt = input_file.suffix.lower().lstrip(".")
    if fmt not in _FORMAT_EXT:
        fmt = "jpg"
    output_file = Path(output_dir) / branded_filename(input_file, _FORMAT_EXT[fmt])

    with Image.open(input_file) as img:
        img = ImageOps.exif_transpose(img).convert("RGBA")
        w, h = img.size

        # Pick a font size proportional to the smaller dimension.
        font_size = max(20, int(min(w, h) / 20))
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except (OSError, IOError):
            font = ImageFont.load_default()

        overlay = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(overlay)

        # Measure text.
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
        except AttributeError:
            tw, th = font.getsize(text)

        margin = max(10, int(min(w, h) * 0.02))

        if position == "diagonal":
            # Render text on a transparent layer, rotate 30°, paste centered.
            text_layer = Image.new("RGBA", (tw + 20, th + 20), (0, 0, 0, 0))
            ImageDraw.Draw(text_layer).text((10, 10), text, font=font, fill=(*rgb, alpha))
            rotated = text_layer.rotate(30, resample=Image.Resampling.BICUBIC, expand=True)
            rx, ry = rotated.size
            overlay.paste(rotated, ((w - rx) // 2, (h - ry) // 2), rotated)
        else:
            if position == "top-left":
                pos = (margin, margin)
            elif position == "top-right":
                pos = (w - tw - margin, margin)
            elif position == "center":
                pos = ((w - tw) // 2, (h - th) // 2)
            elif position == "bottom-left":
                pos = (margin, h - th - margin)
            else:  # bottom-right
                pos = (w - tw - margin, h - th - margin)
            draw.text(pos, text, font=font, fill=(*rgb, alpha))

        composed = Image.alpha_composite(img, overlay)
        if fmt in ("jpg", "jpeg"):
            composed = composed.convert("RGB")
        _save_pil(composed, output_file, fmt, quality=quality)

    return str(output_file)

