import pytest
import os
import shutil
from pathlib import Path

@pytest.fixture
def mock_workspace(tmp_path):
    """
    Creates a temporary workspace with standard directory structure.
    Returns the Path to the workspace root.
    """
    d = tmp_path / "workspace"
    d.mkdir()
    
    (d / "in").mkdir()
    (d / "out").mkdir()
    (d / "config").mkdir()
    
    return d

@pytest.fixture
def mock_config_file(mock_workspace):
    """
    Creates a temporary jobs.yaml in the mock workspace.
    """
    config_path = mock_workspace / "jobs.yaml"
    content = """
defaults:
  input: ~/in
  output: ~/out
  flags:
    force: false

jobs:
  - name: TestJob
    input: ~/test_in
    output: ~/test_out
"""
    config_path.write_text(content, encoding="utf-8")
    return config_path
