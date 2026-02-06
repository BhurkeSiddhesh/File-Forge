import pytest
from docx import Document
from pdf_utils import merge_docx_files
import zipfile
import os

def create_simple_docx(path, text):
    doc = Document()
    doc.add_paragraph(text)
    doc.save(path)

def test_merge_docx_files_with_page_break(tmp_path):
    # Setup
    doc1 = tmp_path / "doc1.docx"
    doc2 = tmp_path / "doc2.docx"
    output = tmp_path / "merged.docx"

    create_simple_docx(str(doc1), "Content 1")
    create_simple_docx(str(doc2), "Content 2")

    # Execute
    merge_docx_files([str(doc1), str(doc2)], str(output))

    # Verify
    assert output.exists()

    # Check for page break XML
    with zipfile.ZipFile(str(output), 'r') as z:
        xml_content = z.read('word/document.xml').decode('utf-8')
        # We expect a page break.
        # Note: python-docx inserts page break as <w:br w:type="page"/>
        assert 'w:type="page"' in xml_content, "Page break not found in merged document"

def test_merge_single_file(tmp_path):
    doc1 = tmp_path / "doc1.docx"
    output = tmp_path / "merged.docx"

    create_simple_docx(str(doc1), "Content 1")

    merge_docx_files([str(doc1)], str(output))

    assert output.exists()

    # Should NOT have a page break (only one doc)
    # Unless there was one in the original doc, which there isn't.
    with zipfile.ZipFile(str(output), 'r') as z:
        xml_content = z.read('word/document.xml').decode('utf-8')
        assert 'w:type="page"' not in xml_content, "Unexpected page break in single file merge"

def test_merge_no_files():
    with pytest.raises(ValueError):
        merge_docx_files([], "output.docx")
