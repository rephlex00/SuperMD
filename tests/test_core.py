
import pytest
from unittest.mock import MagicMock, patch, mock_open
from sn2md.converter import (
    convert_file, 
    process_pages,
    generate_output
)
from sn2md.context import create_context
from sn2md.types import Config, ImageExtractor

@pytest.fixture
def mock_config():
    return Config(
        output_path_template="{{file_basename}}",
        output_filename_template="{{file_basename}}.md",
        template="Content: {{markdown}}",
        model="gpt-4o-test"
    )

class MockExtractor(ImageExtractor):
    def extract_images(self, filename, output_path):
        return [f"{output_path}/page_0.png"]

    def get_notebook(self, filename):
        return MagicMock()

def test_process_pages(mock_config):
    """Test that process_pages iterates images and calls image_to_markdown."""
    
    with patch("sn2md.converter.image_to_markdown", return_value="[Markdown Content]") as mock_i2m:
        pngs = ["page1.png", "page2.png"]
        result = process_pages(pngs, mock_config, "model", progress=False)
        
        assert mock_i2m.call_count == 2
        assert "[Markdown Content]" in result
        
def test_create_context(mock_config):
    """Test context creation logic."""
    pngs = ["/tmp/img1.png"]
    basic_context = {
        "file_basename": "test", 
        "file_name": "test.note",
        "year": "2025"
    }
    
    notebook_mock = MagicMock()
    notebook_mock.links = []
    notebook_mock.keywords = []
    notebook_mock.titles = []
    
    context = create_context(
        notebook_mock, 
        pngs, 
        mock_config, 
        "test.note", 
        "model", 
        "markdown content", 
        basic_context
    )
    
    assert context["markdown"] == "markdown content"
    assert context["images"][0]["name"] == "img1.png"
    assert context["year"] == "2025"

@patch("sn2md.converter.compute_file_hash", return_value="mock_hash")
@patch("sn2md.converter.generate_images")
@patch("sn2md.converter.process_pages")
@patch("sn2md.converter.create_context")
@patch("sn2md.converter.generate_output")
@patch("sn2md.converter.verify_metadata_file")
@patch("os.path.exists", return_value=True) 
@patch("os.path.getmtime", return_value=1234567890.0)
def test_import_supernote_file_core_flow(
    mock_mtime,
    mock_exists,
    mock_verify,
    mock_generate_output, 
    mock_create_context, 
    mock_process_pages, 
    mock_generate_images,
    mock_compute_hash,
    mock_config
):
    """Verify the core flow calls all steps in order."""
    
    # Setup context manager mock
    mock_generate_images.return_value.__enter__.return_value = ["img.png"]
    
    # Should also mock MetadataManager context manager or pass None?
    # import_supernote_file_core instantiates one if None.
    # We can patch MetadataManager
    with patch("sn2md.converter.MetadataManager") as MockManager:
        convert_file(
            MockExtractor(), 
            "test.note", 
            "out_dir", 
            mock_config
        )
        
        mock_verify.assert_called_once()
        mock_process_pages.assert_called_once()
        mock_create_context.assert_called_once()
        mock_generate_output.assert_called_once()
        MockManager.return_value.close.assert_called_once()

@patch("sn2md.converter.compute_file_hash", return_value="mock_hash")
@patch("builtins.open", new_callable=mock_open)
@patch("os.makedirs")
@patch("os.rename")
def test_generate_output(mock_rename, mock_makedirs, mock_file, mock_hash, mock_config):
    """Test output generation (writing file and moving images)."""
    
    context = {
        "file_basename": "test",
        "images": [{"name": "img.png", "link": "attachments/img.png"}],
        "markdown": "content"
    }
    
    from jinja2 import Template
    template = Template(mock_config.template)
    
    mock_manager = MagicMock()
    
    generate_output(
        ["/tmp/img.png"], 
        mock_config, 
        context, 
        "test.note", 
        "/out", 
        template,
        mock_manager,
        "input_hash"
    )
    
    # Verify file write
    mock_file.assert_called()
    handle = mock_file()
    handle.write.assert_called_with("Content: content")
    
    # Verify image move
    mock_rename.assert_called_with("/tmp/img.png", "/out/test/attachments/img.png")
    
    # Verify metadata update
    mock_manager.upsert_entry.assert_called()

@patch("os.path.exists")
def test_verify_metadata_file_reprocess_broken(mock_exists):
    """Test that a missing output file triggers reprocessing even if input hash matches."""
    from sn2md.converter import verify_metadata_file
    from sn2md.metadata_db import InputNotChangedError
    
    mock_manager = MagicMock()
    mock_entry = MagicMock()
    mock_entry.input_file_hash = "same_hash"
    mock_entry.actual_file_path = "/path/to/missing_output.md"
    
    mock_manager.get_entry_by_input.return_value = mock_entry
    
    # Scene: 
    # 1. Entry exists
    # 2. Output file DOES NOT exist
    # 3. Input hash matches
    
    def side_effect(path):
        if path == "/path/to/missing_output.md":
            return False
        return True
    mock_exists.side_effect = side_effect
    
    # Should NOT raise InputNotChangedError
    verify_metadata_file(mock_manager, "test.note", "same_hash")
    
    # Ensure we checked validity
    mock_exists.assert_called_with("/path/to/missing_output.md")

@patch("sn2md.converter.image_to_markdown", return_value="content")
@patch("sn2md.converter.sleep")
def test_process_pages_cooldown(mock_sleep, mock_i2m, mock_config):
    """Test that cooldown sleep is called correct number of times."""
    from sn2md.converter import process_pages
    
    pngs = ["1.png", "2.png", "3.png"]
    process_pages(pngs, mock_config, "model", progress=False, cooldown=0.1)
    
    # Should sleep for ALL pages (3 times total) to ensure gap between files
    assert mock_sleep.call_count == 3
    mock_sleep.assert_called_with(0.1)
    
    # Test with cooldown 0
    mock_sleep.reset_mock()
    process_pages(pngs, mock_config, "model", progress=False, cooldown=0.0)
    mock_sleep.assert_not_called()
