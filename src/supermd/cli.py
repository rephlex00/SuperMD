import os
import sys

import click
from tqdm import tqdm

from supermd import __version__
from supermd.importers import get_extractor

from .converter import (
    convert_directory,
    convert_file,
)

from .config import SuperMDConfig, load_config
from .metadata_db import InputNotChangedError, OutputChangedError
from .ai_utils import MissingAPIKeyError, validate_model_key

from supermd.console import console


def get_config(config_file: str) -> SuperMDConfig:
    try:
        return load_config(config_file)
    except FileNotFoundError:
        console.warning(f"No config file found at {config_file}, using defaults")
    return SuperMDConfig()


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(dir_okay=False),
    default="config/supermd.yaml",
    help="Path to a supermd configuration",
)
@click.option(
    "--output",
    "-o",
    type=click.Path(writable=True),
    default="supernote",
    help="Output directory for images and files (default: supernote)",
)
@click.option(
    "--force",
    "-f",
    is_flag=True,
    help="Force reprocessing even if the notebook hasn't changed.",
)
@click.option(
    "--progress/--no-progress",
    is_flag=True,
    default=True,
    help="Show a progress bar while processing each page.",
)
@click.option(
    "--level",
    "-l",
    default="WARNING",
    help="Set the logging level (e.g., DEBUG, INFO, WARNING, ERROR, CRITICAL)",
)
@click.option(
    "--model",
    "-m",
    default=None,
    help="Set the LLM model (default: gpt-4o-mini)",
)
@click.version_option(__version__, "-v", "--version")
@click.pass_context
def cli(ctx, config, output, force, progress, level, model):
    ctx.obj = {}
    ctx.obj["config"] = get_config(config)
    ctx.obj["output"] = output
    ctx.obj["force"] = force
    ctx.obj["level"] = level
    ctx.obj["model"] = model
    ctx.obj["progress"] = progress
    console.set_level(level)


@cli.command(name="file", help="""
Convert a file to markdown.

Supports Supernote .note and PDF and PNG files.
""")
@click.argument("filename", type=click.Path(readable=True, dir_okay=False))
@click.pass_context
def convert_file_cmd(ctx, filename: str) -> None:
    config = ctx.obj["config"]
    output = ctx.obj["output"]
    force = ctx.obj["force"]
    progress = ctx.obj["progress"]
    model = ctx.obj["model"]

    effective_model = model or config.model
    try:
        validate_model_key(effective_model)
    except MissingAPIKeyError as e:
        console.error(str(e))
        sys.exit(1)

    try:

        if progress:
            pbar_context = tqdm(total=1, desc="Processing", unit="file")
        else:
            from contextlib import nullcontext
            pbar_context = nullcontext()

        with pbar_context as pbar:
            extractor = get_extractor(filename)

            if extractor:
                convert_file(
                    extractor,
                    filename,
                    output,
                    config,
                    force,
                    progress_bar=pbar,
                    model=model,
                    cooldown=5.0
                )
            else:
                console.error(f"Unsupported file format: {filename}")
                sys.exit(1)

    except InputNotChangedError:
        console.info(f"Skipping {filename}: Input not changed")
    except OutputChangedError as e:
        console.warning(f"Refusing to update {filename}: Output modified. Use --force to overwrite. ({e})")
    except ValueError as e:
        console.error(str(e))
        sys.exit(1)


@cli.command(name="directory", help="""
Convert a directory of files to markdown (unsupported file types are ignored).

Equivalent to running `supermd file` on each file in the directory.
""")
@click.argument("directory", type=click.Path(readable=True, file_okay=False))
@click.pass_context
def convert_directory_cmd(ctx, directory: str) -> None:
    config = ctx.obj["config"]
    output = ctx.obj["output"]
    force = ctx.obj["force"]
    progress = ctx.obj["progress"]
    model = ctx.obj["model"]

    effective_model = model or config.model
    try:
        validate_model_key(effective_model)
    except MissingAPIKeyError as e:
        console.error(str(e))
        sys.exit(1)

    convert_directory(directory, output, config, force, progress, model, cooldown=5.0)

@cli.command()
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--dry-run", is_flag=True, help="Preview without running")
@click.option("--debug", is_flag=True, help="Enable verbose debug logging")
def run(config, jobs, dry_run, debug):
    """Run batch conversion jobs"""
    from .batches import run_batches
    run_batches(config, parallelism=jobs, dry_run=dry_run, debug_mode=debug)

@cli.command()
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--delay", "-d", default=30.0, envvar="SUPERMD_WATCH_DELAY", help="Seconds to wait after last change before processing (default: 30.0)")
def watch(config, jobs, delay):
    """Watch for changes and auto-convert"""
    from .watcher import run_watcher
    run_watcher(config, parallelism=jobs, delay=delay)

@cli.command()
@click.option("--config", "-c", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--port", "-p", default=8734, type=int, help="Port for the GUI server (default: 8734)")
def gui(config, port):
    """Launch web-based configuration editor.

    Opens a browser with a form-based GUI for editing the SuperMD YAML
    config file.  Note: saving through the GUI will strip YAML comments.
    """
    from .gui import start_server
    start_server(config, port)


@cli.group()
def meta():
    """Manage metadata"""
    pass

@meta.command(name="list")
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed metadata columns")
def list_meta(config, verbose):
    """List metadata entries"""
    from .config import load_config

    try:
        cfg = load_config(config)
    except FileNotFoundError:
        print(f"Config file not found: {config}")
        sys.exit(66)

    from .report import print_job_report

    for job in cfg.jobs:
        resolved = cfg.resolve_job(job)
        print_job_report(resolved, verbose)

@meta.command(name="rm")
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--dry-run", is_flag=True, help="Preview without running")
def rm_meta(config, dry_run):
    """Remove all metadata entries (reset)"""
    from .config import load_config

    try:
        cfg = load_config(config)
    except FileNotFoundError:
        print(f"Config file not found: {config}")
        sys.exit(66)

    for job in cfg.jobs:
        resolved = cfg.resolve_job(job)
        out_path = resolved["output"]
        print(click.style(f"Cleaning metadata for job: {resolved['name']}", fg="magenta"))

        if not os.path.exists(out_path):
             continue

        from .converter import clean_metadata_directory
        clean_metadata_directory(out_path, dry_run=dry_run)

@meta.command(name="rebuild")
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config file")
@click.option("--dry-run", is_flag=True, help="Preview without running")
def rebuild_meta(config, dry_run):
    """Rebuild metadata files for existing notes"""
    from .config import load_config

    try:
        cfg = load_config(config)
    except FileNotFoundError:
        console.error(f"Config file not found: {config}")
        sys.exit(66)

    console.info(f"Loaded {len(cfg.jobs)} jobs from {config}")

    for job in cfg.jobs:
        resolved = cfg.resolve_job(job)
        console.log(f"Rebuilding metadata for job: {resolved['name']}", fg="blue")

        in_path = resolved["input"]
        out_path = resolved["output"]

        if not os.path.exists(in_path):
            console.log(f"Input path not found: {in_path}", fg="red")
            continue

        from .converter import rebuild_metadata_directory
        rebuild_metadata_directory(in_path, out_path, cfg, dry_run=dry_run)


# ── config / keys ────────────────────────────────────────────────

@cli.group(name="config", help="Manage SuperMD configuration")
def config_group():
    pass


@config_group.group(name="keys", help="Manage LLM API keys")
def keys_group():
    pass


@keys_group.command(name="set")
@click.argument("name")
@click.option("--value", prompt="API key", hide_input=True, help="API key value (prompted if omitted)")
def keys_set(name, value):
    """Store an API key in the llm keystore.

    NAME is the key identifier (e.g. openai, gemini).
    In Docker or CI, prefer setting the corresponding environment variable instead.
    """
    import llm as _llm

    keys_path = _llm.user_dir() / "keys.json"
    import json

    keys = {}
    if keys_path.exists():
        keys = json.loads(keys_path.read_text())
    keys[name] = value
    keys_path.parent.mkdir(parents=True, exist_ok=True)
    keys_path.write_text(json.dumps(keys, indent=2) + "\n")
    console.info(f"Key '{name}' saved to {keys_path}")


@keys_group.command(name="list")
def keys_list():
    """Show which API keys are configured (keystore and environment)."""
    import llm as _llm
    import json

    keys_path = _llm.user_dir() / "keys.json"
    stored = {}
    if keys_path.exists():
        stored = json.loads(keys_path.read_text())
    # Filter out comment entries
    stored = {k: v for k, v in stored.items() if not k.startswith("//")}

    if stored:
        click.echo("Keys in llm keystore:")
        for name in sorted(stored):
            click.echo(f"  {name}: ****{stored[name][-4:]}")
    else:
        click.echo("No keys in llm keystore.")

    # Check common env vars
    env_keys = [
        ("OPENAI_API_KEY", "openai"),
        ("ANTHROPIC_API_KEY", "anthropic"),
        ("GOOGLE_API_KEY", "gemini"),
        ("GEMINI_API_KEY", "gemini"),
    ]
    found_env = []
    for var, provider in env_keys:
        val = os.environ.get(var)
        if val:
            found_env.append((var, provider, f"****{val[-4:]}"))

    if found_env:
        click.echo("\nKeys from environment:")
        for var, provider, masked in found_env:
            click.echo(f"  {var} ({provider}): {masked}")
    elif not stored:
        click.echo("\nNo API keys found. Set one with:")
        click.echo("  supermd config keys set <name>")
        click.echo("  or set an environment variable (e.g. OPENAI_API_KEY)")


@keys_group.command(name="path")
def keys_path():
    """Show the path to the llm keys file."""
    import llm as _llm

    click.echo(_llm.user_dir() / "keys.json")


# ── service ──────────────────────────────────────────────────────

from .service import install_service, uninstall_service, status_service, start_service, stop_service, logs_service

@cli.group()
def service():
    """Manage background service"""
    pass

@service.command()
@click.option("--config", default="config/supermd.yaml", help="Path to supermd.yaml config")
@click.option("--dry-run", is_flag=True, help="Preview plist without installing")
def install(config, dry_run):
    """Install and load the launchd service"""
    install_service(config, dry_run=dry_run)

@service.command()
def uninstall():
    """Unload and remove the launchd service"""
    uninstall_service()

@service.command()
def status():
    """Check status of the background service"""
    status_service()

@service.command()
def start():
    """Start the background service"""
    start_service()

@service.command()
def stop():
    """Stop the background service"""
    stop_service()

@service.command()
@click.option("--lines", "-n", default=10, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(lines, follow):
    """Show service logs"""
    logs_service(lines=lines, follow=follow)

if __name__ == "__main__":
    cli()
