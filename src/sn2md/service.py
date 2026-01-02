import os
import sys
import shutil
from pathlib import Path
from string import Template
import subprocess

PLIST_TEMPLATE = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
  <dict>
    <key>Label</key>
    <string>com.sn2md.watch</string>

    <key>ProgramArguments</key>
    <array>
      <string>$SN2MD_CLI</string>
      <string>watch</string>
      <string>--config</string>
      <string>$CONFIG_PATH</string>
    </array>

    <key>WorkingDirectory</key>
    <string>$PROJECT_DIR</string>

    <key>EnvironmentVariables</key>
    <dict>
      <key>PATH</key>
      <string>$PATH_VAR</string>
      <key>PYTHONPATH</key>
      <string>$PYTHONPATH</string>
    </dict>

    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>

    <key>StandardOutPath</key>
    <string>$HOME/Library/Logs/sn2md-watch.log</string>
    <key>StandardErrorPath</key>
    <string>$HOME/Library/Logs/sn2md-watch.err</string>
  </dict>
</plist>
"""

def generate_plist(config_path: str):
    project_dir = os.getcwd()
    home_dir = os.path.expanduser("~")
    
    # Path to the sn2md-cli executable
    # We want the absolute path to the executable running this script
    sn2md_cli_path = sys.executable 
    # Actually, we are running via `python -m sn2md_app.cli`, but usually we want
    # the entry script if it exists. 
    # However, forcing the python executable + `-m sn2md_app.cli` or similar is safer
    # than relying on a shim that might move.
    # BUT, the pyproject.toml defines a script. Let's try to find it.
    
    # Best bet for now: verify if sys.executable is the venv python.
    # Logic: <venv>/bin/python -> <venv>/bin/sn2md-cli
    
    python_bin = Path(sys.executable)
    possible_cli = python_bin.parent / "sn2md-cli"
    
    if possible_cli.exists():
        executable = str(possible_cli)
    else:
        # Fallback: run via python module
        # Arguments array needs to be constructed differently if we do this, 
        # but the template assumes a single executable string.
        # Let's assume the pip install worked and user has the bin on path or we find it relative.
        executable = shutil.which("sn2md-cli") or str(possible_cli)

    env_path = os.environ.get("PATH", "")
    python_path = os.environ.get("PYTHONPATH", str(Path(project_dir) / "src"))

    template = Template(PLIST_TEMPLATE)
    plist_content = template.substitute(
        SN2MD_CLI=executable,
        CONFIG_PATH=os.path.abspath(config_path),
        PROJECT_DIR=project_dir,
        HOME=home_dir,
        PATH_VAR=env_path,
        PYTHONPATH=python_path
    )
    
    return plist_content

def install_service(config_path: str = "jobs.yaml", dry_run: bool = False):
    plist = generate_plist(config_path)
    
    dest_dir = os.path.expanduser("~/Library/LaunchAgents")
    dest_path = os.path.join(dest_dir, "com.sn2md.watch.plist")
    
    if dry_run:
        print(f"[dry-run] Would write plist to: {dest_path}")
        print(plist)
        return

    os.makedirs(dest_dir, exist_ok=True)
    with open(dest_path, "w", encoding="utf-8") as f:
        f.write(plist)
    
    print(f"Service installed to: {dest_path}")

    # Auto-load the service
    try:
        # Unload first just in case (ignore errors)
        subprocess.run(
            ["launchctl", "unload", dest_path], 
            check=False, 
            stdout=subprocess.DEVNULL, 
            stderr=subprocess.DEVNULL
        )
        
        # Load
        subprocess.run(["launchctl", "load", dest_path], check=True)
        print("Service started successfully.")
    except subprocess.CalledProcessError as e:
        print(f"Error starting service: {e}")
        print("You may need to run manually:")
        print(f"  launchctl load {dest_path}")
    
def uninstall_service():
    dest_path = os.path.expanduser("~/Library/LaunchAgents/com.sn2md.watch.plist")
    if os.path.exists(dest_path):
        subprocess.run(["launchctl", "unload", dest_path], check=False)
        os.remove(dest_path)
        print(f"Service uninstalled: {dest_path}")
    else:
        print("Service not installed.")

def status_service():
    dest_path = os.path.expanduser("~/Library/LaunchAgents/com.sn2md.watch.plist")
    
    # Check if plist exists
    installed = os.path.exists(dest_path)
    print(f"Plist installed: {'Yes' if installed else 'No'} ({dest_path})")
    
    # Check if loaded in launchd
    try:
        # launchctl list returns 0 if found, non-zero if not found
        result = subprocess.run(
            ["launchctl", "list", "com.sn2md.watch"],
            capture_output=True,
            text=True,
            check=False
        )
        
        if result.returncode == 0:
            print("Service status:   LOADED / RUNNING")
            # Parse output for PID or LastExitStatus if desired, but raw output is often enough
            # print(result.stdout)
            
            # Simple PID extraction
            for line in result.stdout.splitlines():
                if '"PID"' in line:
                    pid = line.split()[-1].replace('"', '').replace(';', '')
                    print(f"PID:              {pid}")
                elif '"LastExitStatus"' in line:
                    status = line.split()[-1].replace('"', '').replace(';', '')
                    print(f"Last Exit Status: {status}")
        else:
            print("Service status:   NOT LOADED")
            
    except Exception as e:
        print(f"Error checking status: {e}")

def start_service():
    dest_path = os.path.expanduser("~/Library/LaunchAgents/com.sn2md.watch.plist")
    if not os.path.exists(dest_path):
        print(f"Service plist not found at: {dest_path}")
        print("Please run 'sn2md-cli service install' first.")
        return

    try:
        # Try to load
        subprocess.run(["launchctl", "load", dest_path], check=True, stderr=subprocess.PIPE, text=True)
        print("Service started successfully.")
    except subprocess.CalledProcessError as e:
        if "service already loaded" in e.stderr.lower():
             print("Service is already running.")
        else:
             print(f"Error starting service: {e.stderr.strip()}")

def stop_service():
    dest_path = os.path.expanduser("~/Library/LaunchAgents/com.sn2md.watch.plist")
    
    # We can try to unload even if plist is missing if we know the label, 
    # but launchctl unload typically assumes the plist path for user agents.
    # If the plist is gone, we technically can't unload by path easily in the same way 
    # (though 'bootout' is the modern way, 'unload' is legacy).
    # Sticking to unloading via plist path.
    
    if not os.path.exists(dest_path):
        print(f"Service plist not found at: {dest_path}")
        return

    try:
        subprocess.run(["launchctl", "unload", dest_path], check=True, stderr=subprocess.PIPE, text=True)
        print("Service stopped.")
    except subprocess.CalledProcessError as e:
        if "Could not find specified service" in e.stderr:
             print("Service was not running.")
        else:
             print(f"Error stopping service: {e.stderr.strip()}")

def logs_service(lines: int = 10, follow: bool = False):
    log_path = os.path.expanduser("~/Library/Logs/sn2md-watch.log")
    
    if not os.path.exists(log_path):
        print(f"Log file not found at: {log_path}")
        return

    cmd = ["tail", "-n", str(lines)]
    if follow:
        cmd.append("-f")
    
    cmd.append(log_path)
    
    try:
        # Use simple subprocess call. For -f (follow), this will block until user interrupts.
        subprocess.run(cmd, check=False)
    except KeyboardInterrupt:
        pass
    except Exception as e:
        print(f"Error reading logs: {e}")
