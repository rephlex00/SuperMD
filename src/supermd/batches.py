import os
import sys
import concurrent.futures

from supermd.converter import convert_directory, rebuild_metadata_directory
from supermd.config import SuperMDConfig, JobDefinition, load_config
from supermd.ai_utils import MissingAPIKeyError, validate_model_key
from supermd.console import console


def run_single_job(
    config: SuperMDConfig,
    job: JobDefinition,
    dry_run: bool = False,
    debug_mode: bool = False,
    disable_progress: bool = False,
) -> bool:
    resolved = config.resolve_job(job)
    console.log(f"[job] Starting: {resolved['name']}")

    in_path = resolved["input"]
    out_path = resolved["output"]

    if not os.path.exists(in_path):
        console.log(f"Error: Input path not found: {in_path}")
        return False

    level = "DEBUG" if debug_mode else resolved["level"]

    if dry_run:
        console.log("[dry-run] Configuration check passed.")
        console.log(f"[dry-run] Input: {in_path}")
        console.log(f"[dry-run] Output: {out_path}")

    console.set_level(level)

    progress = False if disable_progress else resolved["progress"]

    try:
        convert_directory(
            directory=in_path,
            output=out_path,
            config=config,
            force=resolved["force"],
            progress=progress,
            model=resolved["model"],
            dry_run=dry_run,
            cooldown=resolved["cooldown"],
        )

        console.log(f"[job {resolved['name']}] SUCCESS")
        return True
    except Exception as e:
        console.log(f"[job {resolved['name']}] FAILED (exception: {e})")
        return False


def run_batches(config_path: str, parallelism: int = 1, dry_run: bool = False, debug_mode: bool = False):
    try:
        config = load_config(config_path)
    except FileNotFoundError:
        console.log(f"Config file not found: {config_path}")
        sys.exit(66)

    jobs = config.jobs
    total = len(jobs)
    console.log(f"supermd: jobs={total} parallel={parallelism} config={config_path}")

    # Log configuration details
    console.log("[config] Defaults:")
    console.log(f"  model: {config.model}")
    console.log(f"  force: {config.defaults.force}")
    console.log(f"  cooldown: {config.defaults.cooldown}s")

    console.log(f"[config] Jobs ({total}):")
    for job in jobs:
        resolved = config.resolve_job(job)
        console.log(f"  - Job '{resolved['name']}':")
        console.log(f"      Input: {resolved['input']}")
        console.log(f"      Output: {resolved['output']}")
        console.log(f"      Process: force={resolved['force']} model={resolved['model']} cooldown={resolved['cooldown']}s")

    # Rebuild metadata so skip logic reflects current input/output state
    console.log("[startup] Rebuilding metadata...")
    for job in jobs:
        resolved = config.resolve_job(job)
        in_path = resolved["input"]
        out_path = resolved["output"]
        if os.path.exists(in_path):
            rebuild_metadata_directory(in_path, out_path, config)
    console.log("[startup] Metadata rebuild complete.")

    # Validate API keys for all models before starting any jobs
    models_seen = set()
    for job in jobs:
        resolved = config.resolve_job(job)
        models_seen.add(resolved["model"])
    for model_name in models_seen:
        try:
            validate_model_key(model_name)
        except MissingAPIKeyError as e:
            console.log(str(e))
            sys.exit(1)

    # Disable progress bars if running in parallel to avoid output corruption
    disable_progress = parallelism > 1

    failures = 0
    with concurrent.futures.ThreadPoolExecutor(max_workers=parallelism) as executor:
        futures = {
            executor.submit(run_single_job, config, job, dry_run, debug_mode, disable_progress): job
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
