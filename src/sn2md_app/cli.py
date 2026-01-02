import click

@click.group()
def main():
    """Supernote to Markdown Converter CLI"""
    pass

from .batches import run_batches

@main.command()
@click.option("--config", default="jobs.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
@click.option("--dry-run", is_flag=True, help="Preview without running")
@click.option("--debug", is_flag=True, help="Enable verbose debug logging")
def run(config, jobs, dry_run, debug):
    """Run batch conversion jobs"""
    run_batches(config, parallelism=jobs, dry_run=dry_run, debug_mode=debug)

from .watcher import run_watcher

@main.command()
@click.option("--config", default="jobs.yaml", help="Path to jobs.yaml config file")
@click.option("--jobs", "-j", default=1, help="Number of parallel jobs")
def watch(config, jobs):
    """Watch for changes and auto-convert"""
    run_watcher(config, parallelism=jobs)

from .service import install_service, uninstall_service

@main.group()
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

from .service import status_service

@service.command()
def status():
    """Check status of the background service"""
    status_service()

from .service import start_service, stop_service

@service.command()
def start():
    """Start the background service"""
    start_service()

@service.command()
def stop():
    """Stop the background service"""
    stop_service()

from .service import logs_service

@service.command()
@click.option("--lines", "-n", default=10, help="Number of lines to show")
@click.option("--follow", "-f", is_flag=True, help="Follow log output")
def logs(lines, follow):
    """Show service logs"""
    logs_service(lines=lines, follow=follow)
