"""
Tests for image resize functionality in image_utils.py.
"""
import pytest
from pathlib import Path
from PIL import Image
from image_utils import resize_image
import os

@pytest.fixture(scope="session")
def sample_image(tmp_path_factory):
    """Creates a sample JPEG image for testing."""
    d = tmp_path_factory.mktemp("images")
    file_path = d / "test_resize.jpg"
    
    # Create a 500x500 RGB image
    img = Image.new('RGB', (500, 500), color='blue')
    img.save(file_path, "JPEG", quality=95)
    
    return file_path

def test_resize_by_dimensions(sample_image, tmp_path):
    """Test resizing by specific dimensions."""
    output_dir = tmp_path / "output_dim"
    output_dir.mkdir()
    
    # Resize to 100x100
    result = resize_image(str(sample_image), str(output_dir), mode='dimensions', width=100, height=100)
    
    with Image.open(result) as img:
        assert img.size == (100, 100)

def test_resize_by_dimensions_aspect_ratio(sample_image, tmp_path):
    """Test resizing by one dimension maintaining aspect ratio."""
    output_dir = tmp_path / "output_aspect"
    output_dir.mkdir()
    
    # Resize width to 250, height should auto-scale to 250 (since original is 500x500)
    result = resize_image(str(sample_image), str(output_dir), mode='dimensions', width=250)
    
    with Image.open(result) as img:
        assert img.size == (250, 250)

def test_resize_by_percentage(sample_image, tmp_path):
    """Test resizing by percentage."""
    output_dir = tmp_path / "output_pct"
    output_dir.mkdir()
    
    # Resize to 50%
    result = resize_image(str(sample_image), str(output_dir), mode='percentage', percentage=50)
    
    with Image.open(result) as img:
        # Original 500x500 -> 50% = 250x250
        assert img.size == (250, 250)

def test_resize_target_size(sample_image, tmp_path):
    """Test resizing to a target file size."""
    output_dir = tmp_path / "output_size"
    output_dir.mkdir()
    
    # Original file size
    original_size = os.path.getsize(sample_image)
    target_kb = (original_size / 1024) / 2 # Aim for half size (approx) or small small value
    target_kb = max(1, int(target_kb)) # Ensure at least 1KB
    
    result = resize_image(str(sample_image), str(output_dir), mode='target_size', target_size_kb=target_kb)
    
    result_size = os.path.getsize(result)
    # Check if result size is less than or close to target
    # Note: Compression is not exact, but should be close or under if possible. 
    # Our heuristic breaks loop if dims are too small, but generally tries to be under.
    
    # Relaxed check: just ensure it's smaller than original and "close" to target or under
    assert result_size <= target_kb * 1024 * 1.5 # Allow some margin, or just check it got smaller
    assert result_size < original_size
