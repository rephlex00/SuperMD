from pathlib import Path
import pytest
from supermd.config import load_config, SuperMDConfig, JobDefinition


@pytest.fixture
def unified_config_file(tmp_path):
    """Creates a temporary supermd.yaml."""
    config_path = tmp_path / "supermd.yaml"
    content = """
model: gpt-4o-mini

defaults:
  force: false
  level: INFO
  cooldown: 5.0

jobs:
  - name: TestJob
    input: ~/test_in
    output: ~/test_out
  - name: OverrideJob
    input: ~/custom_in
    output: ~/custom_out
    model: gemini/flash
    force: true
"""
    config_path.write_text(content, encoding="utf-8")
    return config_path


def test_load_valid_config(unified_config_file):
    """Verify that a valid YAML config is loaded correctly."""
    config = load_config(unified_config_file)
    assert isinstance(config, SuperMDConfig)
    assert config.model == "gpt-4o-mini"
    assert len(config.jobs) == 2
    assert config.jobs[0].name == "TestJob"


def test_load_missing_file():
    """Verify error on missing config file."""
    with pytest.raises(FileNotFoundError):
        load_config("non_existent.yaml")


def test_resolve_job_inherits_defaults(unified_config_file):
    """Verify that resolve_job merges job overrides with config defaults."""
    config = load_config(unified_config_file)

    # First job — inherits everything
    resolved = config.resolve_job(config.jobs[0])
    assert resolved["model"] == "gpt-4o-mini"
    assert resolved["force"] is False
    assert resolved["cooldown"] == 5.0

    # Second job — overrides model and force
    resolved2 = config.resolve_job(config.jobs[1])
    assert resolved2["model"] == "gemini/flash"
    assert resolved2["force"] is True
    assert resolved2["cooldown"] == 5.0  # inherited


def test_defaults_used_when_empty():
    """Verify SuperMDConfig has sensible defaults."""
    config = SuperMDConfig()
    assert config.model == "gpt-4o-mini"
    assert config.defaults.force is False
    assert config.defaults.cooldown == 5.0
    assert config.jobs == []
