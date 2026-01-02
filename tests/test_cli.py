
import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock
from sn2md.cli import cli

@pytest.fixture
def runner():
    return CliRunner()

@patch("sn2md.cli.import_supernote_file_core")
def test_cli_file(mock_core, runner):
    """Test 'file' command invokes core importer."""
    result = runner.invoke(cli, ["file", "test.note"])
    assert result.exit_code == 0
    mock_core.assert_called()

@patch("sn2md.cli.import_supernote_directory_core")
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
    mock_run.assert_called_with("jobs.yaml", parallelism=1, dry_run=True, debug_mode=False)

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
    mock_install.assert_called_with("jobs.yaml", dry_run=True)
