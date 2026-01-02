
import os
import sys
from sn2md_app.batches import tilde_expand, run_single_job
from sn2md_app.config import JobConfig, JobFlags

def test_tilde_expand():
    """Verify tilde expansion."""
    home = os.path.expanduser("~")
    assert tilde_expand("~/foo") == os.path.join(home, "foo")
    assert tilde_expand("/abs/path") == "/abs/path"
    assert tilde_expand("") == ""

def test_run_single_job_dry_run_construction(capsys, monkeypatch):
    """
    Verify dry-run logging shows parameters.
    """
    job = JobConfig(
        name="Test",
        input="~/in",
        output="~/out",
        flags=JobFlags(force=True, level="DEBUG")
    )
    
    # Mock os.path.exists to return True
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    
    success = run_single_job(job, dry_run=True)
    assert success is True
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "[dry-run] Would run conversion:" in output
    assert "[dry-run] Level: DEBUG" in output
    assert "[dry-run] Force: True" in output
    
    # Check paths expanded
    home = os.path.expanduser("~")
    expected_in = os.path.join(home, "in")
    assert expected_in in output

def test_run_single_job_direct_execution(monkeypatch):
    """
    Verify run_single_job calls import_supernote_directory_core directly.
    """
    job = JobConfig(
        name="Test",
        input="/tmp/in",
        output="/tmp/out",
        flags=JobFlags(progress=True)
    )
    monkeypatch.setattr(os.path, "exists", lambda p: True)

    called_args = {}

    def mock_core(directory, output, config, force, progress, model):
        called_args["directory"] = directory
        called_args["output"] = output
        called_args["progress"] = progress
        
    def mock_setup(level):
        pass
        
    def mock_get_config(config_file):
        pass

    # Mock sn2md imports in sn2md_app.batches
    monkeypatch.setattr("sn2md_app.batches.import_supernote_directory_core", mock_core)
    monkeypatch.setattr("sn2md_app.batches.setup_logging", mock_setup)
    monkeypatch.setattr("sn2md_app.batches.get_config", mock_get_config)
    
    run_single_job(job, dry_run=False, disable_progress=False)
    
    assert called_args["directory"] == "/tmp/in"
    assert called_args["output"] == "/tmp/out"
    assert called_args["progress"] is True
    
def test_run_single_job_disable_progress(monkeypatch):
    """
    Verify progress is disabled when requested (e.g. for parallel jobs).
    """
    job = JobConfig(
        name="Test",
        input="/tmp/in",
        output="/tmp/out",
        flags=JobFlags(progress=True)
    )
    monkeypatch.setattr(os.path, "exists", lambda p: True)

    called_args = {}
    def mock_core(*args, **kwargs):
        called_args.update(kwargs)
        # Capture positional args if necessary, but we used keywords in call
        if not kwargs and len(args) >= 5:
             called_args["progress"] = args[4]
             
    # Since we use keyword args in implementation:
    # import_supernote_directory_core(directory=..., progress=...)
    def mock_core_kwargs(directory, output, config, force, progress, model):
        called_args["progress"] = progress

    monkeypatch.setattr("sn2md_app.batches.import_supernote_directory_core", mock_core_kwargs)
    monkeypatch.setattr("sn2md_app.batches.setup_logging", lambda l: None)
    
    # Run with disable_progress=True
    run_single_job(job, dry_run=False, disable_progress=True)
    
    assert called_args["progress"] is False
