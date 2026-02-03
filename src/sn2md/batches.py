
import os
import sys
import concurrent.futures
import click
import re
from datetime import datetime
from pathlib import Path
from typing import List

# Direct imports from sn2md
from sn2md.converter import convert_directory
from sn2md.cli import setup_logging, get_config
from sn2md.types import Config
from sn2md.console import console

from .job_config import load_jobs_config, merge_defaults, JobConfig


def tilde_expand(path_str: str) -> str:
    if not path_str:
        return ""
    return os.path.expanduser(path_str)

def run_single_job(job: JobConfig, dry_run: bool = False, debug_mode: bool = False, disable_progress: bool = False) -> bool:
    console.log(f"[job] Starting: {job.name}")
    
    in_path = tilde_expand(job.input)
    out_path = tilde_expand(job.output)
    cfg_path = tilde_expand(job.config) if job.config else None
    
    if not os.path.exists(in_path):
        console.log(f"Error: Input path not found: {in_path}")
        return False

    # Determine logging level
    level = "DEBUG" if debug_mode else job.flags.level

    if dry_run:
        console.log(f"[dry-run] Configuration check passed.")
        console.log(f"[dry-run] Input: {in_path}")
        console.log(f"[dry-run] Output: {out_path}")
        
    setup_logging(level)

    # Prepare configuration object
    if cfg_path:
        config = get_config(cfg_path)
    else:
        config = Config()

    # Determine progress bar state
    progress = False if disable_progress else job.flags.progress
    
    # Load env file if specified
    if job.env_file:
         env_path = tilde_expand(job.env_file)
         if os.path.exists(env_path):
             # Basic .env parsing manually since we are in the same process
             # python-dotenv is better but let's stick to what we had or simple parsing
             with open(env_path) as f:
                for line in f:
                    line = line.strip()
                    if line and not line.startswith("#") and "=" in line:
                        k, v = line.split("=", 1)
                        os.environ[k] = v

    try:
        convert_directory(
            directory=in_path,
            output=out_path,
            config=config,
            force=job.flags.force,
            progress=progress,
            model=job.flags.model,
            dry_run=dry_run,
            cooldown=job.flags.cooldown
        )
        
        console.log(f"[job {job.name}] SUCCESS")
        return True
    except Exception as e:
        console.log(f"[job {job.name}] FAILED (exception: {e})")
        return False

def run_batches(config_path: str, parallelism: int = 1, dry_run: bool = False, debug_mode: bool = False):
    try:
        batch_config = load_jobs_config(config_path)
    except FileNotFoundError:
        console.log(f"Config file not found: {config_path}")
        sys.exit(66)
        
    defaults = batch_config.defaults
    jobs = []
    for job_data in batch_config.jobs:
        jobs.append(merge_defaults(job_data, defaults))
        
    total = len(jobs)
    console.log(f"sn2md-cli: jobs={total} parallel={parallelism} config={config_path}")

    # Log Configuration Details
    console.log("[config] Loaded Defaults:")
    for k, v in defaults.items():
        if k != "flags":
            console.log(f"  {k}: {v}")
    if "flags" in defaults:
        console.log("  flags:")
        for k, v in defaults["flags"].items():
             console.log(f"    {k}: {v}")
             
    console.log(f"[config] Jobs ({total}):")
    for job in jobs:
        console.log(f"  - Job '{job.name}':")
        console.log(f"      Input: {job.input}")
        console.log(f"      Output: {job.output}")
        # Only log flags that differ from defaults or are interesting? 
        # For now, just logging key flags for clarity
        console.log(f"      Process: force={job.flags.force} model={job.flags.model} cooldown={job.flags.cooldown}s")

    
    # Disable progress bars if running in parallel to avoid output corruption
    disable_progress = parallelism > 1
    
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {
            executor.submit(run_single_job, job, dry_run, debug_mode, disable_progress): job 
            for job in jobs
        }
        
        for future in concurrent.futures.as_completed(futures):
            success = future.result()
            if not success:
                failures += 1
    
    msg = f"All done. total={total} ok={total - failures} err={failures}"
    color = "green" if failures == 0 else "red"
    console.log(msg, fg=color)
    
    if failures > 0:
        sys.exit(1)
