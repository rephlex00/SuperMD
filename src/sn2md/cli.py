import logging
import sys
import tomllib

import click
from platformdirs import user_config_dir

from sn2md.importers.atelier import AtelierExtractor
from sn2md.importers.pdf import PDFExtractor
from sn2md.importers.png import PNGExtractor
from sn2md import __version__

from .importer import (
    logger as importer_logger,
    import_supernote_directory_core,
    import_supernote_file_core,
)
from .importers.note import NotebookExtractor
from .types import Config
from .metadata import InputNotChangedError, OutputChangedError

logger = logging.getLogger(__name__)


def setup_logging(level):
    logging.basicConfig(
        level=level,
        format="[%(levelname)s] %(message)s",
        force=True
    )

    logger.setLevel(level)
    importer_logger.setLevel(level)
    logger.debug(f"Logging level: {level}")


    # Suppress PIL debugging
    pil_logger = logging.getLogger('PIL.PngImagePlugin')
    pil_logger.setLevel(logging.WARNING)


def get_config(config_file: str) -> Config:
    try:
        with open(config_file, "rb") as f:
            data = tomllib.load(f)
            file_config = Config(**data)
            return file_config
    except FileNotFoundError:
        print(f"No config file found at {config_file}, using defaults", file=sys.stderr)

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
        if filename.lower().endswith(".note"):
            import_supernote_file_core(NotebookExtractor(), filename, output, config, force, progress, model)
        elif filename.lower().endswith(".pdf"):
            import_supernote_file_core(PDFExtractor(), filename, output, config, force, progress, model)
        elif filename.lower().endswith(".png"):
            import_supernote_file_core(PNGExtractor(), filename, output, config, force, progress, model)
        elif filename.lower().endswith(".spd"):
            import_supernote_file_core(AtelierExtractor(), filename, output, config, force, progress, model)
        else:
            print("Unsupported file format")
            sys.exit(1)
    except InputNotChangedError:
        logger.info(f"Skipping {filename}: Input not changed")
    except OutputChangedError as e:
        print(click.style(f"Refusing to update {filename}: Output file has been modified locally. Use --force to overwrite.", fg="yellow"))
        logger.warning(f"Skipping {filename}: {e}")
    except ValueError as e:
        print(e)
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
    import_supernote_directory_core(directory, output, config, force, progress, model)

@cli.command()
@click.option("--config", default="jobs.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--dry-run", is_flag=True, help="Preview without running")
@click.option("--debug", is_flag=True, help="Enable verbose debug logging")
def run(config, jobs, dry_run, debug):
    """Run batch conversion jobs"""
    from .batches import run_batches
    run_batches(config, parallelism=jobs, dry_run=dry_run, debug_mode=debug)

@cli.command()
@click.option("--config", default="jobs.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
def watch(config, jobs):
    """Watch for changes and auto-convert"""
    from .watcher import run_watcher
    run_watcher(config, parallelism=jobs)

from .service import install_service, uninstall_service, status_service, start_service, stop_service, logs_service

@cli.group()
def service():
    """Manage background service"""
    pass

@service.command()
@click.option("--config", default="jobs.yaml", help="Path to jobs.yaml config")
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
