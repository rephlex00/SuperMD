import os
import sys
import subprocess
import concurrent.futures
import click
import re
from datetime import datetime
from pathlib import Path
from typing import List
from .config import load_jobs_config, merge_defaults, JobConfig

def log(msg: str, fg: str = None):
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ts_prefix = f"[{ts}]"
    ts_colored = click.style(ts_prefix, fg="bright_black")
    
    # Calculate indent for subsequent lines (timestamp length + 1 space)
    indent_len = len(ts_prefix) + 1
    indent_str = " " * indent_len

    if fg:
        # Override from caller (legacy/explicit)
        # Apply color to all lines
        lines = msg.splitlines()
        first = lines[0]
        click.echo(f"{ts_colored} {click.style(first, fg=fg)}")
        for line in lines[1:]:
             click.echo(f"{indent_str}{click.style(line, fg=fg)}")
        return

    # 1. Parse Tag from first line
    lines = msg.splitlines()
    first_line = lines[0]
    
    tag_match = re.match(r"^(\[[^\]]+\])\s*(.*)$", first_line)
    tag_colored = ""
    body_str = first_line
    tag_sub_indent = "" # extra indent if tag was stripped

    if tag_match:
        tag_str = tag_match.group(1)
        body_str = tag_match.group(2)
        tag_sub_indent = " " * (len(tag_str) + 1)
        
        # Color tag based on content
        if "dry-run" in tag_str:
            tag_colored = click.style(tag_str, fg="cyan")
        elif "job" in tag_str or "watch" in tag_str:
            tag_colored = click.style(tag_str, fg="blue")
        else:
            tag_colored = click.style(tag_str, fg="magenta")

    # Helper to style body content
    def style_body(text):
        res = text
        if "SUCCESS" in text:
             res = text.replace("SUCCESS", click.style("SUCCESS", fg="green", bold=True))
        elif "FAILED" in text:
             res = text.replace("FAILED", click.style("FAILED", fg="red", bold=True))
        elif "Error" in text:
             res = click.style(text, fg="red")
        else:
            # Key-Value styling
            kv_match = re.match(r"^([A-Za-z0-9 _-]+):\s+(.*)$", text)
            if kv_match:
                label = kv_match.group(1)
                value = kv_match.group(2)
                label_colored = click.style(f"{label}:", fg="bright_black")
                
                if value.startswith("/") or value.startswith("~") or "directory" in value:
                     value_colored = click.style(value, fg="yellow")
                else:
                     value_colored = value
                res = f"{label_colored} {value_colored}"
            elif "sn2md-cli" in text:
                 res = click.style(text, fg="magenta")
        return res

    # Style first line body
    body_colored = style_body(body_str)
    
    if tag_colored:
        click.echo(f"{ts_colored} {tag_colored} {body_colored}")
    else:
        click.echo(f"{ts_colored} {body_colored}")
        
    # Process subsequent lines
    # Indent them to align with body of first line (past timestamp and tag)
    # or just past timestamp? User asked "indented properly".
    # Aligning past timestamp defines the block. 
    # Aligning past tag might be too much indent for generic text, but good for "Would run:" properties.
    
    full_indent = indent_str + tag_sub_indent
    
    for line in lines[1:]:
        # Style each line individually?
        # Often subsequent lines are multiline values.
        # Let's apply simple highlighting if it looks like a path/command
        stripped = line.strip()
        styled_line = line 
        if stripped.startswith("-") or stripped.startswith("/"):
             # It's an arg or path
             styled_line = click.style(line, fg="yellow")
        
        click.echo(f"{full_indent}{styled_line}")


def tilde_expand(path_str: str) -> str:
    if not path_str:
        return ""
    return os.path.expanduser(path_str)

def run_single_job(job: JobConfig, dry_run: bool = False) -> bool:
    log(f"[job] Starting: {job.name}")
    
    in_path = tilde_expand(job.input)
    out_path = tilde_expand(job.output)
    cfg_path = tilde_expand(job.config) if job.config else None
    
    if not os.path.exists(in_path):
        log(f"Error: Input path not found: {in_path}")
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
        # Format command nicely for readability
        # Just putting args on separate lines if it's long?
        # Or just break it a bit.
        cmd_pretty = " ".join(cmd)
        if len(cmd_pretty) > 80:
             # Basic wrapping/formatting
             # Split on major flags?
             cmd_pretty = " ".join(cmd).replace(" -", "\n-")
             
        log(f"[dry-run] Would run:\n{cmd_pretty}")
        log(f"[dry-run] Input: {in_path}")
        log(f"[dry-run] Output: {out_path}")
        return True
        
    try:
        # Run subprocess
        result = subprocess.run(cmd, env=env, check=False)
        if result.returncode == 0:
            log(f"[job {job.name}] SUCCESS")
            return True
        else:
            log(f"[job {job.name}] FAILED (exit code {result.returncode})")
            return False
    except Exception as e:
        log(f"[job {job.name}] FAILED (exception: {e})")
        return False

def run_batches(config_path: str, parallelism: int = 1, dry_run: bool = False):
    try:
        batch_config = load_jobs_config(config_path)
    except FileNotFoundError:
        log(f"Config file not found: {config_path}")
        sys.exit(66)
        
    defaults = batch_config.defaults
    jobs = []
    for job_data in batch_config.jobs:
        jobs.append(merge_defaults(job_data, defaults))
        
    total = len(jobs)
    log(f"sn2md-cli: jobs={total} parallel={parallelism} config={config_path}")
    
    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {executor.submit(run_single_job, job, dry_run): job for job in jobs}
        for future in concurrent.futures.as_completed(futures):
            success = future.result()
            if not success:
                failures += 1
    
    msg = f"All done. total={total} ok={total - failures} err={failures}"
    color = "green" if failures == 0 else "red"
    log(msg, fg=color)
    
    if failures > 0:
        sys.exit(1)
