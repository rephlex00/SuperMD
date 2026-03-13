import os
import re
from supermd.batches import run_single_job
from supermd.config import SuperMDConfig, JobDefinition, ProcessingDefaults


def test_run_single_job_dry_run(capsys, monkeypatch):
    """Verify dry-run logging shows parameters."""
    config = SuperMDConfig(
        defaults=ProcessingDefaults(force=True, level="DEBUG")
    )
    job = JobDefinition(name="Test", input="~/in", output="~/out")

    monkeypatch.setattr(os.path, "exists", lambda p: True)
    monkeypatch.setattr("supermd.batches.convert_directory", lambda *args, **kwargs: None)

    success = run_single_job(config, job, dry_run=True)
    assert success is True

    captured = capsys.readouterr()
    ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
    clean_output = ansi_escape.sub('', captured.out)

    assert "[dry-run] Configuration check passed." in clean_output

    home = os.path.expanduser("~")
    expected_in = os.path.join(home, "in")
    assert expected_in in captured.out


def test_run_single_job_direct_execution(monkeypatch):
    """Verify run_single_job calls convert_directory."""
    config = SuperMDConfig(
        defaults=ProcessingDefaults(progress=True)
    )
    job = JobDefinition(name="Test", input="/tmp/in", output="/tmp/out")

    monkeypatch.setattr(os.path, "exists", lambda p: True)

    called_args = {}

    def mock_core(directory, output, config, force, progress, model, dry_run, cooldown):
        called_args["directory"] = directory
        called_args["output"] = output
        called_args["progress"] = progress

    monkeypatch.setattr("supermd.batches.convert_directory", mock_core)

    run_single_job(config, job, dry_run=False, disable_progress=False)

    assert called_args["directory"] == "/tmp/in"
    assert called_args["output"] == "/tmp/out"
    assert called_args["progress"] is True


def test_run_single_job_disable_progress(monkeypatch):
    """Verify progress is disabled when requested (e.g. for parallel jobs)."""
    config = SuperMDConfig(
        defaults=ProcessingDefaults(progress=True)
    )
    job = JobDefinition(name="Test", input="/tmp/in", output="/tmp/out")

    monkeypatch.setattr(os.path, "exists", lambda p: True)

    called_args = {}

    def mock_core(directory, output, config, force, progress, model, dry_run, cooldown):
        called_args["progress"] = progress

    monkeypatch.setattr("supermd.batches.convert_directory", mock_core)

    run_single_job(config, job, dry_run=False, disable_progress=True)

    assert called_args["progress"] is False
