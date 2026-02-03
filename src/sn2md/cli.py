import sys
import tomllib


import click
from platformdirs import user_config_dir
from tqdm import tqdm

from sn2md.importers.atelier import AtelierExtractor
from sn2md.importers.pdf import PDFExtractor
from sn2md.importers.png import PNGExtractor
from sn2md import __version__

from .converter import (
    convert_directory,
    convert_file,
)
from .importers.note import NotebookExtractor

from .types import Config
from .metadata_db import InputNotChangedError, OutputChangedError, MetadataManager

from sn2md.console import console

def setup_logging(level):
    console.set_level(level)


def get_config(config_file: str) -> Config:
    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
            file_config = Config(**data)
            return file_config
    except FileNotFoundError:
        console.warning(f"No config file found at {config_file}, using defaults")

    return Config()


@click.group()
@click.option(
    "--config",
    "-c",
    type=click.Path(dir_okay=False),
    default=user_config_dir() + "/sn2md.toml",
    help="Path to a sn2md configuration",
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
    setup_logging(level)



@cli.command(name="file", help="""
Convert a file to markdown.

Supports Supernote .note and PDF and PNG files.
""")
@click.argument("filename", type=click.Path(readable=True, dir_okay=False))
@click.pass_context
def import_supernote_file(ctx, filename: str) -> None:
    config = ctx.obj["config"]
    output = ctx.obj["output"]
    force = ctx.obj["force"]
    progress = ctx.obj["progress"]
    model = ctx.obj["model"]
    try:

        if progress:
            pbar_context = tqdm(total=1, desc="Processing", unit="file")
        else:
            from contextlib import nullcontext
            pbar_context = nullcontext()

        with pbar_context as pbar:
            extractor = None
            if filename.lower().endswith(".note"):
                extractor = NotebookExtractor()
            elif filename.lower().endswith(".pdf"):
                extractor = PDFExtractor()
            elif filename.lower().endswith(".png"):
                extractor = PNGExtractor()
            elif filename.lower().endswith(".spd"):
                extractor = AtelierExtractor()
            
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

Equivalent to running `sn2md file` on each file in the directory.
""")
@click.argument("directory", type=click.Path(readable=True, file_okay=False))
@click.pass_context
def import_supernote_directory(ctx, directory: str) -> None:
    config = ctx.obj["config"]
    output = ctx.obj["output"]
    force = ctx.obj["force"]
    progress = ctx.obj["progress"]
    model = ctx.obj["model"]
    convert_directory(directory, output, config, force, progress, model, cooldown=5.0)

@cli.command()
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--dry-run", is_flag=True, help="Preview without running")
@click.option("--debug", is_flag=True, help="Enable verbose debug logging")
def run(config, jobs, dry_run, debug):
    """Run batch conversion jobs"""
    from .batches import run_batches
    run_batches(config, parallelism=jobs, dry_run=dry_run, debug_mode=debug)

@cli.command()
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--delay", "-d", default=30.0, envvar="SN2MD_WATCH_DELAY", help="Seconds to wait after last change before processing (default: 30.0)")
def watch(config, jobs, delay):
    """Watch for changes and auto-convert"""
    from .watcher import run_watcher
    run_watcher(config, parallelism=jobs, delay=delay)

@cli.group()
def meta():
    """Manage metadata"""
    pass

@meta.command(name="list")
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config file")
@click.option("--verbose", "-v", is_flag=True, help="Show detailed metadata columns")
def list_meta(config, verbose):
    """List metadata entries"""
    from .job_config import load_jobs_config, merge_defaults
    import os
    
    try:
        batch_config = load_jobs_config(config)
    except FileNotFoundError:
        print(f"Config file not found: {config}")
        sys.exit(66)

    defaults = batch_config.defaults
    
    from .report import print_job_report
    
    for job_data in batch_config.jobs:
        job = merge_defaults(job_data, defaults)
        print_job_report(job, verbose)

@meta.command(name="rm")
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config file")
@click.option("--dry-run", is_flag=True, help="Preview without running")
def rm_meta(config, dry_run):
    """Remove all metadata entries (reset)"""
    from .job_config import load_jobs_config, merge_defaults
    import os
    
    try:
        batch_config = load_jobs_config(config)
    except FileNotFoundError:
        print(f"Config file not found: {config}")
        sys.exit(66)
        
    defaults = batch_config.defaults
    
    for job_data in batch_config.jobs:
        job = merge_defaults(job_data, defaults)
        out_path = os.path.expanduser(job.output)
        print(click.style(f"Cleaning metadata for job: {job.name}", fg="magenta"))
        
        if not os.path.exists(out_path):
             continue
             
        from .converter import clean_metadata_directory
        clean_metadata_directory(out_path, dry_run=dry_run)

@meta.command(name="rebuild")
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config file")
@click.option("--dry-run", is_flag=True, help="Preview without running")
def rebuild_meta(config, dry_run):
    """Rebuild metadata files for existing notes"""
    from .job_config import load_jobs_config, merge_defaults
    import os
    
    try:
        batch_config = load_jobs_config(config)
    except FileNotFoundError:
        console.error(f"Config file not found: {config}")
        sys.exit(66)

    defaults = batch_config.defaults
    console.info(f"Loaded {len(batch_config.jobs)} jobs from {config}")

    for job_data in batch_config.jobs:
        job = merge_defaults(job_data, defaults)
        console.log(f"Rebuilding metadata for job: {job.name}", fg="blue")
        
        in_path = os.path.expanduser(job.input)
        out_path = os.path.expanduser(job.output)
        
        if not os.path.exists(in_path):
            console.log(f"Input path not found: {in_path}", fg="red")
            continue

        # Load config for templates
        cfg_path = os.path.expanduser(job.config) if job.config else None
        if cfg_path:
            job_config_obj = get_config(cfg_path)
        else:
            # Load default config (global settings) if no specific job config
            job_config_obj = get_config(user_config_dir() + "/sn2md.toml") 

        from .converter import rebuild_metadata_directory
        rebuild_metadata_directory(in_path, out_path, job_config_obj, dry_run=dry_run)


from .service import install_service, uninstall_service, status_service, start_service, stop_service, logs_service

@cli.group()
def service():
    """Manage background service"""
    pass

@service.command()
@click.option("--config", default="config/jobs.local.yaml", help="Path to jobs.yaml config")
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
