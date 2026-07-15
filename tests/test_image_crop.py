"""
Tests for image cropping functionality in image_utils.py.
"""
import pytest
from pathlib import Path
from PIL import Image
from scripts.image_utils import crop_image

@pytest.fixture(scope="session")
def sample_crop_image(tmp_path_factory):
    """Creates a sample 100x100 RED image for testing."""
    d = tmp_path_factory.mktemp("images_crop")
    file_path = d / "test_crop.jpg"
    
    img = Image.new('RGB', (100, 100), color='red')
    img.save(file_path, "JPEG", quality=95)
    
    return file_path

def test_crop_basic(sample_crop_image, tmp_path):
    """Test basic cropping."""
    output_dir = tmp_path / "output_crop"
    output_dir.mkdir()
    
    # Crop top-left 50x50
    result = crop_image(str(sample_crop_image), str(output_dir), x=0, y=0, width=50, height=50)
    
    with Image.open(result) as img:
        assert img.size == (50, 50)

def test_crop_center(sample_crop_image, tmp_path):
    """Test cropping from center."""
    output_dir = tmp_path / "output_crop_center"
    output_dir.mkdir()
    
    # Crop 25x25 from middle (starts at 37, 37 approx)
    result = crop_image(str(sample_crop_image), str(output_dir), x=37, y=37, width=25, height=25)
    
    with Image.open(result) as img:
        assert img.size == (25, 25)

def test_crop_out_of_bounds(sample_crop_image, tmp_path):
    """Test cropping with bounds larger than image."""
    output_dir = tmp_path / "output_crop_bounds"
    output_dir.mkdir()
    
    # Request 200x200 starting at 50,50 (extends past 100,100)
    # Result should be clipped to image boundaries -> 50x50
    result = crop_image(str(sample_crop_image), str(output_dir), x=50, y=50, width=200, height=200)
    
    with Image.open(result) as img:
        assert img.size == (50, 50)


def test_crop_negative_x_clamped(sample_crop_image, tmp_path):
    """Negative x coordinate is clamped to 0."""
    output_dir = tmp_path / "output_crop_neg_x"
    output_dir.mkdir()

    # x=-10 should be treated as x=0; width=50 from x=0 -> 50 wide
    result = crop_image(str(sample_crop_image), str(output_dir), x=-10, y=0, width=50, height=50)

    with Image.open(result) as img:
        assert img.size == (50, 50)


def test_crop_negative_y_clamped(sample_crop_image, tmp_path):
    """Negative y coordinate is clamped to 0."""
    output_dir = tmp_path / "output_crop_neg_y"
    output_dir.mkdir()

    result = crop_image(str(sample_crop_image), str(output_dir), x=0, y=-20, width=50, height=50)

    with Image.open(result) as img:
        assert img.size == (50, 50)


def test_crop_output_filename_contains_cropped(sample_crop_image, tmp_path):
    """Output filename contains '_cropped' suffix."""
    output_dir = tmp_path / "output_crop_name"
    output_dir.mkdir()

    result = crop_image(str(sample_crop_image), str(output_dir), x=0, y=0, width=50, height=50)

    assert "_cropped" in Path(result).name


def test_crop_full_image(sample_crop_image, tmp_path):
    """Cropping the full image dimensions returns the original size."""
    output_dir = tmp_path / "output_crop_full"
    output_dir.mkdir()

    result = crop_image(str(sample_crop_image), str(output_dir), x=0, y=0, width=100, height=100)

    with Image.open(result) as img:
        assert img.size == (100, 100)


def test_crop_produces_jpeg(sample_crop_image, tmp_path):
    """Cropped output is saved as JPEG."""
    output_dir = tmp_path / "output_crop_fmt"
    output_dir.mkdir()

    result = crop_image(str(sample_crop_image), str(output_dir), x=0, y=0, width=50, height=50)

    assert result.endswith(".jpg")
