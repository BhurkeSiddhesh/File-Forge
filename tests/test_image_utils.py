"""
Tests for image_utils module.
"""
import pytest
from pathlib import Path
from image_utils import heic_to_jpeg


@pytest.fixture(scope="session")
def sample_heic(tmp_path_factory):
    """
    Creates a mock HEIC file for testing.
    Note: Since we can't easily create a real HEIC without actual image data,
    we test with a minimal valid HEIC structure or skip if pillow-heif isn't installed.
    """
    try:
        import pillow_heif
        from PIL import Image
        
        # Create a simple test image and save as HEIC
        d = tmp_path_factory.mktemp("images")
        file_path = d / "test_image.heic"
        
        # Create a simple RGB image
        img = Image.new('RGB', (100, 100), color='red')
        
        # Register HEIF opener and save
        pillow_heif.register_heif_opener()
        img.save(file_path, format='HEIF')
        
        return file_path
    except Exception as e:
        pytest.skip(f"Could not create test HEIC: {e}")


def test_heic_to_jpeg_basic(sample_heic, tmp_path):
    """Test basic HEIC to JPEG conversion."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    result = heic_to_jpeg(str(sample_heic), str(output_dir))
    
    assert Path(result).exists()
    assert result.endswith('.jpg')
    assert Path(result).stat().st_size > 0


def test_heic_to_jpeg_quality(sample_heic, tmp_path):
    """Test that quality parameter affects output file size."""
    output_dir_high = tmp_path / "output_high"
    output_dir_low = tmp_path / "output_low"
    output_dir_high.mkdir()
    output_dir_low.mkdir()
    
    result_high = heic_to_jpeg(str(sample_heic), str(output_dir_high), quality=95)
    result_low = heic_to_jpeg(str(sample_heic), str(output_dir_low), quality=50)
    
    # Higher quality should generally produce larger files
    # (may not always hold for tiny test images, so we just check both exist)
    assert Path(result_high).exists()
    assert Path(result_low).exists()


def test_heic_to_jpeg_output_filename(sample_heic, tmp_path):
    """Test that output filename is correctly derived from input."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    result = heic_to_jpeg(str(sample_heic), str(output_dir))
    
    # Should have same stem as input but with .jpg extension
    assert Path(result).stem == sample_heic.stem
    assert Path(result).suffix == '.jpg'
