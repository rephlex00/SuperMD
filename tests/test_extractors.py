
import pytest
from unittest.mock import MagicMock, patch
from sn2md.importers.note import NotebookExtractor
from sn2md.importers.pdf import PDFExtractor
from sn2md.importers.png import PNGExtractor

# --- NotebookExtractor Tests ---

@patch("sn2md.importers.note.load_notebook")
@patch("sn2md.importers.note.convert_notebook_to_pngs")
def test_notebook_extractor_extract(mock_convert, mock_load):
    """Verify NotebookExtractor loads and converts notebook."""
    extractor = NotebookExtractor()
    mock_convert.return_value = ["img1.png"]
    
    result = extractor.extract_images("test.note", "out_dir")
    
    mock_load.assert_called_with("test.note")
    mock_convert.assert_called()
    assert result == ["img1.png"]

@patch("sn2md.importers.note.load_notebook")
def test_notebook_extractor_get_notebook(mock_load):
    """Verify loading notebook object."""
    extractor = NotebookExtractor()
    extractor.get_notebook("test.note")
    mock_load.assert_called_with("test.note")

# --- PNGExtractor Tests ---

@patch("shutil.copy")
def test_png_extractor_extract(mock_copy):
    """Verify PNG extractor copies file."""
    extractor = PNGExtractor()
    result = extractor.extract_images("/tmp/test.png", "/out")
    
    mock_copy.assert_called_with("/tmp/test.png", "/out/test.png")
    assert result == ["/out/test.png"]

def test_png_extractor_get_notebook():
    """Verify PNG extractor returns None for notebook."""
    assert PNGExtractor().get_notebook("test") is None


# --- PDFExtractor Tests ---

@patch("pymupdf.open")
def test_pdf_extractor_extract(mock_open):
    """Verify MOck PDF extraction."""
    extractor = PDFExtractor()
    
    # Mock PDF document and pages
    mock_doc = MagicMock()
    mock_doc.page_count = 1
    page_mock = MagicMock()
    page_mock.number = 0
    mock_doc.__iter__.return_value = [page_mock]
    mock_open.return_value = mock_doc
    
    result = extractor.extract_images("test.pdf", "/out")
    
    mock_open.assert_called_with("test.pdf")
    # Verify save called on pixmap
    page_mock.get_pixmap.return_value.save.assert_called()
    assert result[0].endswith(".png")
