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

def test_run_single_job_command_construction(capsys, monkeypatch):
    """
    Verify command construction without executing subprocess.
    """
    job = JobConfig(
        name="Test",
        input="~/in",
        output="~/out",
        flags=JobFlags(force=True, level="DEBUG")
    )
    
    # Mock os.path.exists to return True
    monkeypatch.setattr(os.path, "exists", lambda p: True)
    
    # We use dry_run=True to inspect the printed command logic 
    # which proves the args were assembled.
    success = run_single_job(job, dry_run=True)
    assert success is True
    
    captured = capsys.readouterr()
    output = captured.out
    
    assert "[dry-run] Would run:" in output
    assert "-m sn2md" in output
    assert "--force" in output
    assert "-l DEBUG" in output
    
    # Check paths expanded
    home = os.path.expanduser("~")
    expected_in = os.path.join(home, "in")
    assert expected_in in output

def test_run_single_job_subprocess_call(monkeypatch):
    """
    Verify run_single_job actually calls subprocess.run with correct args.
    """
    job = JobConfig(
        name="Test",
        input="/tmp/in",
        output="/tmp/out",
    )
    monkeypatch.setattr(os.path, "exists", lambda p: True)

    class MockResult:
        returncode = 0
        
    called_args = []
    
    def mock_run(cmd, env=None, check=False):
        called_args.append(cmd)
        return MockResult()
        
    import subprocess
    monkeypatch.setattr(subprocess, "run", mock_run)
    
    run_single_job(job, dry_run=False)
    
    assert len(called_args) == 1
    cmd_list = called_args[0]
    
    assert sys.executable in cmd_list
    assert "-m" in cmd_list
    assert "sn2md" in cmd_list
    assert "/tmp/in" in cmd_list
