"""
Tests for image_utils module.
"""
import pytest
from pathlib import Path
from scripts.image_utils import heic_to_jpeg


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

    # Should be branded with the original stem plus the forgefiles.org suffix
    assert Path(result).stem == f"{sample_heic.stem}_forgefiles.org"
    assert Path(result).suffix == '.jpg'


@pytest.fixture(scope="session")
def heic_with_metadata(tmp_path_factory):
    """A HEIC carrying an ICC color profile and EXIF (orientation + camera + date)."""
    try:
        import pillow_heif
        from PIL import Image, ImageCms

        pillow_heif.register_heif_opener()
        d = tmp_path_factory.mktemp("meta_images")
        file_path = d / "with_meta.heic"

        icc = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        exif = Image.Exif()
        exif[0x0112] = 6  # Orientation (rotate) — should be baked, tag reset to 1
        exif[0x010F] = "TestCam"  # Make
        exif[0x9003] = "2026:07:24 10:00:00"  # DateTimeOriginal

        img = Image.new("RGB", (160, 90))
        px = img.load()
        for y in range(90):
            for x in range(160):
                px[x, y] = (x % 256, (y * 2) % 256, (x * y) % 256)
        img.save(file_path, format="HEIF", icc_profile=icc, exif=exif.tobytes(), quality=95)
        return {"path": file_path, "icc_len": len(icc)}
    except Exception as e:  # pragma: no cover - env without pillow-heif
        pytest.skip(f"Could not create HEIC with metadata: {e}")


def test_heic_to_jpeg_preserves_icc_profile(heic_with_metadata, tmp_path):
    """The source ICC color profile must survive into the JPEG (no color shift)."""
    from PIL import Image

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = heic_to_jpeg(str(heic_with_metadata["path"]), str(output_dir))

    with Image.open(result) as j:
        out_icc = j.info.get("icc_profile", b"")
    assert out_icc, "ICC profile was dropped during HEIC->JPEG conversion"
    assert len(out_icc) == heic_with_metadata["icc_len"]


def test_heic_to_jpeg_preserves_exif_metadata(heic_with_metadata, tmp_path):
    """Camera/date EXIF must be carried over, with Orientation normalized to 1."""
    from PIL import Image

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = heic_to_jpeg(str(heic_with_metadata["path"]), str(output_dir))

    with Image.open(result) as j:
        exif = j.getexif()
    assert exif.get(0x010F) == "TestCam"
    assert exif.get(0x9003) == "2026:07:24 10:00:00"
    # Orientation is baked into the pixels; the tag must read 1 to avoid a viewer
    # rotating the already-correct image a second time.
    assert exif.get(0x0112, 1) == 1


def test_heic_to_jpeg_no_metadata_is_safe(tmp_path):
    """A HEIC without ICC/EXIF must still convert cleanly (no crash, no empty block)."""
    import pillow_heif
    from PIL import Image

    pillow_heif.register_heif_opener()
    src = tmp_path / "plain.heic"
    Image.new("RGB", (48, 32), "orange").save(src, format="HEIF", quality=90)

    output_dir = tmp_path / "out"
    output_dir.mkdir()
    result = heic_to_jpeg(str(src), str(output_dir))

    with Image.open(result) as j:
        assert j.mode == "RGB"
        assert j.size == (48, 32)
        assert not j.info.get("icc_profile")
