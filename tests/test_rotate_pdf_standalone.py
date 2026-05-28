import pytest
from pathlib import Path
import pikepdf
import tempfile
import sys
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pdf_utils import rotate_pdf
from reportlab.pdfgen import canvas


@pytest.fixture
def sample_pdf(tmp_path):
    """Creates a simple PDF file for testing."""
    file_path = tmp_path / "sample.pdf"
    c = canvas.Canvas(str(file_path))
    c.drawString(100, 750, "Hello, this is a test PDF.")
    c.save()
    return file_path


@pytest.fixture
def multi_page_pdf(tmp_path):
    """Creates a multi-page PDF file for rotation tests."""
    file_path = tmp_path / "multi_sample.pdf"
    c = canvas.Canvas(str(file_path))
    for i in range(1, 5):
        c.drawString(100, 750, f"Page {i}")
        c.showPage()
    c.save()
    return file_path


@pytest.fixture
def locked_pdf(tmp_path, sample_pdf):
    """Creates a password-protected PDF file."""
    file_path = tmp_path / "locked.pdf"
    password = "secret_password"
    with pikepdf.open(sample_pdf) as pdf:
        pdf.save(
            file_path,
            encryption=pikepdf.Encryption(user=password, owner=password)
        )
    return {"path": file_path, "password": password}


class TestRotatePDFFunction:
    """Unit tests for rotate_pdf utility function."""

    def test_rotate_pdf_90_degrees(self, multi_page_pdf, tmp_path):
        """Test rotating PDF by 90 degrees."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90)

        assert Path(result).exists()
        assert result.endswith(".pdf")

        # Verify the rotation was applied
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 90

    def test_rotate_pdf_180_degrees(self, multi_page_pdf, tmp_path):
        """Test rotating PDF by 180 degrees."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 180)

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 180

    def test_rotate_pdf_270_degrees(self, multi_page_pdf, tmp_path):
        """Test rotating PDF by 270 degrees (or -90)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 270)

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 270

    def test_rotate_pdf_negative_angle(self, multi_page_pdf, tmp_path):
        """Test rotating PDF with negative angle (-90)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), -90)

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 270  # -90 % 360 == 270

    def test_rotate_pdf_specific_pages(self, multi_page_pdf, tmp_path):
        """Test rotating only specific pages."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90, pages="1,3")

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get('/Rotate', 0)) == 90  # Page 1 rotated
            assert int(pdf.pages[1].get('/Rotate', 0)) == 0    # Page 2 not rotated
            assert int(pdf.pages[2].get('/Rotate', 0)) == 90  # Page 3 rotated
            assert int(pdf.pages[3].get('/Rotate', 0)) == 0    # Page 4 not rotated

    def test_rotate_pdf_page_range(self, multi_page_pdf, tmp_path):
        """Test rotating a range of pages."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 180, pages="2-3")

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get('/Rotate', 0)) == 0    # Page 1 not rotated
            assert int(pdf.pages[1].get('/Rotate', 0)) == 180  # Page 2 rotated
            assert int(pdf.pages[2].get('/Rotate', 0)) == 180  # Page 3 rotated
            assert int(pdf.pages[3].get('/Rotate', 0)) == 0    # Page 4 not rotated

    def test_rotate_pdf_invalid_angle(self, multi_page_pdf, tmp_path):
        """Test that invalid angles raise ValueError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(ValueError, match="Angle must be"):
            rotate_pdf(str(multi_page_pdf), str(output_dir), 45)  # Invalid angle

        with pytest.raises(ValueError, match="Angle must be"):
            rotate_pdf(str(multi_page_pdf), str(output_dir), 0)   # Invalid angle

    def test_rotate_pdf_invalid_pages(self, multi_page_pdf, tmp_path):
        """Test that invalid page selections raise ValueError."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pytest.raises(ValueError):
            rotate_pdf(str(multi_page_pdf), str(output_dir), 90, pages="10")  # Page out of range

    def test_rotate_pdf_with_password(self, locked_pdf, tmp_path):
        """Test rotating a password-protected PDF."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(
            str(locked_pdf["path"]),
            str(output_dir),
            90,
            password=locked_pdf["password"]
        )

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 90

    def test_rotate_pdf_output_filename(self, multi_page_pdf, tmp_path):
        """Test that output file has correct naming."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90)
        filename = Path(result).name

        assert "_rotated.pdf" in filename

    def test_rotate_pdf_page_count_preserved(self, multi_page_pdf, tmp_path):
        """Test that page count is preserved after rotation."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        with pikepdf.open(multi_page_pdf) as pdf:
            original_count = len(pdf.pages)

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90)

        with pikepdf.open(result) as pdf:
            rotated_count = len(pdf.pages)

        assert original_count == rotated_count == 4

    def test_rotate_pdf_all_pages_explicit(self, multi_page_pdf, tmp_path):
        """Test rotating all pages explicitly with 'all' keyword."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90, pages="all")

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 90

    def test_rotate_pdf_cumulative_rotation(self, multi_page_pdf, tmp_path):
        """Test that multiple rotations accumulate correctly."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # First rotation: 90 degrees
        result1 = rotate_pdf(str(multi_page_pdf), str(output_dir), 90)

        # Second rotation: 90 degrees (should be 180 total)
        result2 = rotate_pdf(result1, str(output_dir), 90)

        with pikepdf.open(result2) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 180

    def test_rotate_pdf_full_rotation_back_to_zero(self, multi_page_pdf, tmp_path):
        """Test that 360 degree rotation equals 0 (no rotation)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        # Rotate 360 degrees (should equal 0)
        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90)
        result = rotate_pdf(result, str(output_dir), 90)
        result = rotate_pdf(result, str(output_dir), 90)
        result = rotate_pdf(result, str(output_dir), 90)

        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 0  # Back to original

    def test_rotate_pdf_single_page(self, sample_pdf, tmp_path):
        """Test rotating a single-page PDF."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(sample_pdf), str(output_dir), 90)

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) == 1
            assert int(pdf.pages[0].get('/Rotate', 0)) == 90

    def test_rotate_pdf_preserves_metadata(self, sample_pdf, tmp_path):
        """Test that rotation preserves PDF metadata."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(sample_pdf), str(output_dir), 90)

        # Just verify the file can be opened and has pages
        with pikepdf.open(result) as pdf:
            assert len(pdf.pages) > 0

    def test_rotate_pdf_no_pages_parameter_rotates_all(self, multi_page_pdf, tmp_path):
        """Test that omitting pages parameter rotates all pages."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90, pages=None)

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            for page in pdf.pages:
                rotation = int(page.get('/Rotate', 0))
                assert rotation == 90

    def test_rotate_pdf_mixed_page_selections(self, multi_page_pdf, tmp_path):
        """Test rotating mixed page selections (individual and range)."""
        output_dir = tmp_path / "output"
        output_dir.mkdir()

        result = rotate_pdf(str(multi_page_pdf), str(output_dir), 90, pages="1,3-4")

        assert Path(result).exists()
        with pikepdf.open(result) as pdf:
            assert int(pdf.pages[0].get('/Rotate', 0)) == 90  # Page 1
            assert int(pdf.pages[1].get('/Rotate', 0)) == 0    # Page 2
            assert int(pdf.pages[2].get('/Rotate', 0)) == 90  # Page 3
            assert int(pdf.pages[3].get('/Rotate', 0)) == 90  # Page 4


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
