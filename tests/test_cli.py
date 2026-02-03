
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from sn2md.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch("sn2md.cli.convert_file")
def test_cli_file(mock_core, runner):
    """Test 'file' command invokes core importer."""
    result = runner.invoke(cli, ["file", "test.note"])
    assert result.exit_code == 0
    mock_core.assert_called()

@patch("sn2md.cli.convert_directory")
def test_cli_directory(mock_core, runner):
    """Test 'directory' command invokes directory importer."""
    result = runner.invoke(cli, ["directory", "test_dir"])
    assert result.exit_code == 0
    mock_core.assert_called()

@patch("sn2md.batches.run_batches")
def test_cli_run(mock_run, runner):
    """Test 'run' command invokes batch runner."""
    result = runner.invoke(cli, ["run", "--dry-run"])
    assert result.exit_code == 0
    mock_run.assert_called_with("config/jobs.local.yaml", parallelism=1, dry_run=True, debug_mode=False)

@patch("sn2md.watcher.run_watcher")
def test_cli_watch(mock_watch, runner):
    """Test 'watch' command invokes watcher."""
    result = runner.invoke(cli, ["watch"])
    assert result.exit_code == 0
    mock_watch.assert_called()

@patch("sn2md.cli.install_service")
def test_cli_service_install(mock_install, runner):
    """Test 'service install' command."""
    result = runner.invoke(cli, ["service", "install", "--dry-run"])
    assert result.exit_code == 0
    mock_install.assert_called_with("config/jobs.local.yaml", dry_run=True)

@patch("sn2md.cli.start_service")
def test_cli_service_start(mock_start, runner):
    """Test 'service start' command."""
    result = runner.invoke(cli, ["service", "start"])
    assert result.exit_code == 0
    mock_start.assert_called()

@patch("sn2md.cli.stop_service")
def test_cli_service_stop(mock_stop, runner):
    """Test 'service stop' command."""
    result = runner.invoke(cli, ["service", "stop"])
    assert result.exit_code == 0
    mock_stop.assert_called()

@patch("sn2md.cli.logs_service")
def test_cli_service_logs(mock_logs, runner):
    """Test 'service logs' command."""
    result = runner.invoke(cli, ["service", "logs"])
    assert result.exit_code == 0
    mock_logs.assert_called()

@patch("sn2md.report.MetadataManager")
def test_cli_meta_list(mock_manager_cls, runner):
    """Test 'meta list' command."""
    mock_manager = mock_manager_cls.return_value
    # The CLI calls get_all_entries(), not list()
    mock_entry = MagicMock()
    mock_entry.input_note_filename = "test.note"
    mock_entry.actual_file_path = "/path/to/test.md"
    mock_entry.is_locked = False
    mock_entry.image_files = [] # avoid len() error or similar
    
    mock_manager.get_all_entries.return_value = [mock_entry]
    
    with patch("os.path.exists") as mock_exists:
        # Simulate output file missing
        mock_exists.side_effect = lambda p: p != "/path/to/test.md"
        
        result = runner.invoke(cli, ["meta", "list"])
        assert result.exit_code == 0
        assert "Broken" in result.output
    
    mock_manager.get_all_entries.assert_called()

@patch("sn2md.converter.rebuild_metadata_directory")
def test_cli_meta_rebuild(mock_rebuild, runner):
    """Test 'meta rebuild' command."""
    # The CLI imports this function inside the command handler, so we patch where it is defined.
    result = runner.invoke(cli, ["meta", "rebuild"])
    assert result.exit_code == 0
    mock_rebuild.assert_called()

@patch("sn2md.converter.clean_metadata_directory")
def test_cli_meta_rm(mock_clean, runner):
    """Test 'meta rm' command."""
    # The CLI imports this function inside the command handler.
    result = runner.invoke(cli, ["meta", "rm"], input="y")
    assert result.exit_code == 0
    mock_clean.assert_called()
