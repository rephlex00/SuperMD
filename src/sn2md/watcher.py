import os
import time
import sys
import subprocess
from pathlib import Path
from watchdog.observers import Observer
from watchdog.events import FileSystemEventHandler
from .batches import run_batches, log

class DebouncedEventHandler(FileSystemEventHandler):
    def __init__(self, callback, debounce_interval=2.0):
        self.callback = callback
        self.debounce_interval = debounce_interval
        self.last_event_time = 0
        self.timer_running = False

    def on_any_event(self, event):
        if event.is_directory:
            return
            
        current_time = time.time()
        if (current_time - self.last_event_time) > self.debounce_interval:
            log(f"[watch] Detected change: {event.src_path}")
            self.last_event_time = current_time
            self.callback()

def run_watcher(config_path: str, parallelism: int = 1):
    log(f"[watch] Starting watcher using config: {config_path}")
    
    # Run once at startup
    run_batches(config_path, parallelism)
    
    # Setup watchdog
    # Note: We need to know which directories to watch.
    # Parsing config to find input directories
    from .job_config import load_jobs_config
    try:
        batch_config = load_jobs_config(config_path)
    except Exception as e:
        log(f"Error loading config: {e}")
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
        log("No input directories found to watch.")
        return

    log(f"[watch] Watching directories: {', '.join(watch_dirs)}")
    
    event_handler = DebouncedEventHandler(
        callback=lambda: run_batches(config_path, parallelism)
    )
    
    observer = Observer()
    for path in watch_dirs:
        if os.path.exists(path):
            observer.schedule(event_handler, path, recursive=True)
        else:
            log(f"[watch] Warning: Watch path does not exist: {path}")

    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
