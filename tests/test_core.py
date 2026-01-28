
import pytest
from unittest.mock import MagicMock, patch, mock_open
from sn2md.importer import (
    import_supernote_file_core, 
    create_context, 
    process_pages,
    generate_output
)
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
    
    with patch("sn2md.importer.image_to_markdown", return_value="[Markdown Content]") as mock_i2m:
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

@patch("sn2md.importer.compute_file_hash", return_value="mock_hash")
@patch("sn2md.importer.generate_images")
@patch("sn2md.importer.process_pages")
@patch("sn2md.importer.create_context")
@patch("sn2md.importer.generate_output")
@patch("sn2md.importer.verify_metadata_file")
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
    with patch("sn2md.importer.MetadataManager") as MockManager:
        import_supernote_file_core(
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

@patch("sn2md.importer.compute_file_hash", return_value="mock_hash")
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
