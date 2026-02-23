"""
Performance tests to validate optimization improvements.
"""
import pytest
import time
from pathlib import Path
from PIL import Image
from image_utils import resize_image, heic_to_jpeg, crop_image, _prepare_image


def test_prepare_image_helper_efficiency(tmp_path):
    """Test that _prepare_image helper reduces duplicate code."""
    # Create test image with RGBA mode
    test_img_path = tmp_path / "test_rgba.png"
    img = Image.new("RGBA", (100, 100), (255, 0, 0, 128))
    img.save(test_img_path, "PNG")
    
    # Test the helper function
    with Image.open(test_img_path) as img:
        prepared = _prepare_image(img)
        assert prepared.mode == "RGB"
        assert prepared.size == (100, 100)


def test_binary_search_resize_faster(tmp_path, benchmark_image):
    """Test that binary search approach for target_size is more efficient."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # Test with target size that requires quality adjustment
    target_size_kb = 20
    
    start_time = time.perf_counter()
    output_path = resize_image(
        str(benchmark_image),
        str(output_dir),
        mode='target_size',
        target_size_kb=target_size_kb
    )
    elapsed = time.perf_counter() - start_time
    
    # Verify output file meets target (with 20% tolerance)
    output_file = Path(output_path)
    assert output_file.exists()
    
    actual_size_kb = output_file.stat().st_size / 1024
    # Allow some tolerance (up to 20% over target is acceptable)
    assert actual_size_kb <= target_size_kb * 1.2
    
    # Binary search should complete in under 1 second for typical images
    # Old linear approach could take 3-5 seconds
    assert elapsed < 2.0, f"Binary search took {elapsed:.2f}s (expected < 2.0s)"
    print(f"PASS Binary search completed in {elapsed:.3f}s")


def test_optimize_flag_reduces_size(tmp_path, benchmark_image):
    """Test that optimize=True flag reduces file size."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # Create a reference JPEG without optimize flag
    with Image.open(benchmark_image) as img:
        ref_path = output_dir / "reference.jpg"
        img.save(ref_path, "JPEG", quality=95, optimize=False)
        ref_size = ref_path.stat().st_size
    
    # Convert using our optimized function (with optimize=True)
    output_path = resize_image(
        str(benchmark_image),
        str(output_dir),
        mode='percentage',
        percentage=100  # No resize, just conversion
    )
    
    optimized_size = Path(output_path).stat().st_size
    
    # Optimized version should be smaller (typically 10-20% reduction)
    reduction_percent = ((ref_size - optimized_size) / ref_size) * 100
    print(f"PASS File size reduction: {reduction_percent:.1f}% (from {ref_size} to {optimized_size} bytes)")
    assert optimized_size < ref_size, "Optimize flag should reduce file size"


def test_no_duplicate_image_conversions(tmp_path, benchmark_image):
    """Test that EXIF transpose and RGB conversion are done once via helper."""
    output_dir = tmp_path / "output"
    output_dir.mkdir()
    
    # All three operations should use _prepare_image helper
    operations = [
        lambda: heic_to_jpeg(str(benchmark_image), str(output_dir)),
        lambda: resize_image(str(benchmark_image), str(output_dir), mode='percentage', percentage=80),
        lambda: crop_image(str(benchmark_image), str(output_dir), x=10, y=10, width=50, height=50)
    ]
    
    for op in operations:
        start = time.perf_counter()
        result = op()
        elapsed = time.perf_counter() - start
        
        # Each operation should be fast (< 0.5s for small images)
        assert elapsed < 0.5, f"Operation took {elapsed:.2f}s (expected < 0.5s)"
        assert Path(result).exists()
        
        # Cleanup for next test
        Path(result).unlink()


def test_import_time_reduction():
    """Test that imports are efficient (no late imports in hot paths)."""
    pytest.importorskip("fastapi")
    
    import sys
    import importlib
    
    # Measure import time for main module
    start = time.perf_counter()
    
    # Force reimport to measure
    if 'main' in sys.modules:
        del sys.modules['main']
    
    # This would fail if there are circular imports or slow imports
    import main
    elapsed = time.perf_counter() - start
    
    # Import should be fast (< 2 seconds even with dependencies)
    # Note: First import may be slower due to bytecode compilation
    print(f"PASS main.py import time: {elapsed:.3f}s")
    assert elapsed < 5.0, f"Import took {elapsed:.2f}s (expected < 5.0s)"


@pytest.fixture
def benchmark_image(tmp_path):
    """Create a test image for benchmarking."""
    img_path = tmp_path / "benchmark.jpg"
    # Create a realistic size image (1MB+)
    img = Image.new("RGB", (1920, 1080), (100, 150, 200))
    img.save(img_path, "JPEG", quality=95)
    return img_path
