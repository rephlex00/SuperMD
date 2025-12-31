import os
import sys
import subprocess
import concurrent.futures
from pathlib import Path
from typing import List
from .config import load_jobs_config, merge_defaults, JobConfig

def tilde_expand(path_str: str) -> str:
    if not path_str:
        return ""
    return os.path.expanduser(path_str)

def run_single_job(job: JobConfig, dry_run: bool = False) -> bool:
    print(f"[job] Starting: {job.name}")
    
    in_path = tilde_expand(job.input)
    out_path = tilde_expand(job.output)
    cfg_path = tilde_expand(job.config) if job.config else None
    
    if not os.path.exists(in_path):
        print(f"Error: Input path not found: {in_path}")
        return False
        
    # Construct arguments for sn2md
    cmd = [sys.executable, "-m", "sn2md", "directory", in_path, "-o", out_path]
    
    if cfg_path:
        cmd.extend(["-c", cfg_path])
    else:
        # Pass flags if no config file
        cmd.extend(["-m", job.flags.model])
        cmd.extend(["-l", job.flags.level])
        if job.flags.force:
            cmd.append("--force")
        if job.flags.progress:
            cmd.append("--progress")
        else:
            cmd.append("--no-progress")
            
    cmd.extend(job.extra_args)
    
    # Environment variables
    env = os.environ.copy()
    env["PYTHONPATH"] = str(Path(__file__).parent.parent) # Ensure src/ is in path
    
    if job.env_file:
        env_file = tilde_expand(job.env_file)
        if os.path.exists(env_file):
            # Simple env file parsing
            with open(env_file) as f:
                for line in f:
                    if "=" in line and not line.strip().startswith("#"):
                        key, val = line.strip().split("=", 1)
                        env[key] = val

    if dry_run:
        print(f"[dry-run] Would run: {' '.join(cmd)}")
        print(f"[dry-run] Input: {in_path}")
        print(f"[dry-run] Output: {out_path}")
        return True
        
    try:
        # Run subprocess
        result = subprocess.run(cmd, env=env, check=False)
        if result.returncode == 0:
            print(f"[job {job.name}] SUCCESS")
            return True
        else:
            print(f"[job {job.name}] FAILED (exit code {result.returncode})")
            return False
    except Exception as e:
        print(f"[job {job.name}] FAILED (exception: {e})")
        return False

def run_batches(config_path: str, parallelism: int = 1, dry_run: bool = False):
    try:
        batch_config = load_jobs_config(config_path)
    except FileNotFoundError:
        print(f"Config file not found: {config_path}")
        sys.exit(66)
        
    defaults = batch_config.defaults
    jobs = []
    for job_data in batch_config.jobs:
        jobs.append(merge_defaults(job_data, defaults))
        
    total = len(jobs)
    print(f"sn2md-cli: jobs={total} parallel={parallelism} config={config_path}")
    
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(run_single_job, job, dry_run): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            success = future.result()
            if not success:
                failures += 1
                
    print(f"All done. total={total} ok={total - failures} err={failures}")
    if failures > 0:
        sys.exit(1)
