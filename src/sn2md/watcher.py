import os
import time
import sys
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .batches import run_batches
from sn2md.console import console

class DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_change_time = 0
        self.has_pending_changes = False

    def on_any_event(self, event):
        if event.is_directory:
            return
            
        if event.event_type not in ('created', 'modified', 'moved'):
            return

        def is_hidden(path):
            parts = path.split(os.sep)
            return any(part.startswith(".") and part not in (".", "..") for part in parts)

        # For moves, we fundamentally care about the destination
        if event.event_type == 'moved':
            if is_hidden(event.dest_path):
                return
        else:
             # For created/modified, check source
             if is_hidden(event.src_path):
                 return

        self.last_change_time = time.time()
        if not self.has_pending_changes:
            self.has_pending_changes = True
            console.log(f"[watch] Detected change ({event.event_type}): {event.src_path} (waiting for stability)")
        else:
             # Don't spam logs for every subsequent change file
             pass

def run_watcher(config_path: str, parallelism: int = 1, delay: float = 30.0):
    console.log(f"[watch] Starting watcher using config: {config_path}")
    console.log(f"[watch] Delay set to {delay} seconds")
    
    # Setup watchdog
    # Note: We need to know which directories to watch.
    # Parsing config to find input directories
    from .job_config import load_jobs_config
    try:
        batch_config = load_jobs_config(config_path)
    except Exception as e:
        console.log(f"Error loading config: {e}")
        return

    # Collect unique input directories
    watch_dirs = set()
    defaults = batch_config.defaults
    for job in batch_config.jobs:
        # Merge basic defaults
        input_dir = job.get("input", defaults.get("input"))
        if input_dir:
            watch_dirs.add(os.path.expanduser(input_dir))
            
    if not watch_dirs:
        console.log("No input directories found to watch.")
        return

    console.log(f"[watch] Watching directories: {', '.join(watch_dirs)}")
    
    event_handler = DebouncedEventHandler()
    
    observer = Observer()
    for path in watch_dirs:
        if os.path.exists(path):
            observer.schedule(event_handler, path, recursive=True)
        else:
            console.log(f"[watch] Warning: Watch path does not exist: {path}")

    observer.start()
    try:
        while True:
            time.sleep(1)
            if event_handler.has_pending_changes:
                current_time = time.time()
                time_since_change = current_time - event_handler.last_change_time
                
                if time_since_change >= delay:
                    console.log(f"[watch] Stability reached ({time_since_change:.1f}s >= {delay}s), processing...")
                    # Reset pending state BEFORE running to catch updates during processing
                    event_handler.has_pending_changes = False
                    # Run batches
                    run_batches(config_path, parallelism)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
