from pathlib import Path
import pytest
from sn2md_app.config import load_jobs_config, merge_defaults, JobConfig, BatchConfig

def test_load_valid_config(mock_config_file):
    """Verify that a valid YAML config is loaded correctly."""
    config = load_jobs_config(mock_config_file)
    assert isinstance(config, BatchConfig)
    assert config.defaults["input"] == "~/in"
    assert len(config.jobs) == 1
    assert config.jobs[0]["name"] == "TestJob"

def test_load_missing_file():
    """Verify error on missing config file."""
    with pytest.raises(FileNotFoundError):
        load_jobs_config("non_existent.yaml")

def test_merge_defaults():
    """Verify that job config overrides defaults correctly."""
    defaults = {
        "input": "~/default_in",
        "output": "~/default_out",
        "flags": {"force": False, "level": "INFO"}
    }
    
    # job overrides input and one flag
    job_data = {
        "name": "OverrideJob",
        "input": "~/custom_in",
        "flags": {"force": True}
    }
    
    merged = merge_defaults(job_data, defaults)
    assert isinstance(merged, JobConfig)
    
    # Check overridden
    assert merged.input == "~/custom_in"
    assert merged.flags.force is True
    
    # Check inherited
    assert merged.output == "~/default_out"
    assert merged.flags.level == "INFO"

def test_merge_extra_args():
    """Verify extra_args are concatenated."""
    defaults = {"input": "foo", "output": "bar", "extra_args": ["--foo"]}
    job = {"input": "baz", "extra_args": ["--bar"]}
    
    merged = merge_defaults(job, defaults)
    assert merged.extra_args == ["--foo", "--bar"]
