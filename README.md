# sn2md-app

A unified Python application for converting Supernote files to Markdown, orchestrating batch jobs, and syncing via background service.

This project replaces the legacy `sn2md-batches.sh` script with a proper Python CLI (`sn2md-cli`) and vendors the `sn2md` library to ensure stability and portability.

## Features

- **Batch Processing**: Run multiple conversion jobs via `jobs.yaml`.
- **Background Watcher**: Monitors input directories and auto-converts new files using `watchdog`.
- **Service Management**: Easily install/uninstall launchd agents on macOS.
- **Docker Support**: Run as a containerized service with `docker-compose`.
- **Portable**: No hardcoded paths; dependencies managed via `pyproject.toml`.
- **Robustness**: Validates inputs, handles errors gracefully, and provides clear logs.

## Installation

### Local Installation

1. Create a virtual environment and install the project:
   ```bash
   python3 -m venv .venv
   source .venv/bin/activate
   pip install -e .
   ```

2. Bootstrap local models (if using Ollama):
   ```bash
   # Ensure ollama is running
   sn2md-cli run --dry-run
   ```

## Configuration

1. Copy the example configuration:
   ```bash
   cp config/jobs.example.yaml jobs.yaml
   ```
2. Edit `jobs.yaml` to set your input/output paths and other preferences.
   - `input_dir`: Path to folder containing `.note` files.
   - `output_dir`: Path where markdown files will be saved.
   - `model`: (Optional) AI model to use for transcription.

## Usage

### Run Batch Jobs
Process all jobs defined in `jobs.yaml` once:
```bash
sn2md-cli run
```
Options:
- `--dry-run`: Preview actions without writing files.
- `--jobs N`: Run `N` jobs in parallel (default: 1).
- `--config path/to/jobs.yaml`: Use a different config file.

### Watch Mode
Watch input directories for changes and auto-run conversions:
```bash
sn2md-cli watch --config jobs.yaml
```

### Background Service (macOS)
Install the watcher as a background LaunchAgent so it runs automatically:

1. Install the service:
   ```bash
   sn2md-cli service install
   ```
2. Check status:
   ```bash
   sn2md-cli service status
   ```
3. View logs:
   ```bash
   sn2md-cli service logs
   ```
4. Uninstall:
   ```bash
   sn2md-cli service uninstall
   ```

Note: Logs are written to `~/Library/Logs/sn2md-watch.log`.

## Docker Usage

Run the application in a container to avoid dependency issues.

1. **Build the image**:
   ```bash
   docker-compose build
   ```

2. **Configure volumes**:
   Update `docker-compose.yml` to map your local directories to the container:
   ```yaml
   volumes:
     - /path/to/local/in:/data/in
     - /path/to/local/out:/data/out
     - ./config:/config
   ```

3. **Run the watcher**:
   ```bash
   docker-compose up -d
   ```

4. **View logs**:
   ```bash
   docker-compose logs -f
   ```

## Troubleshooting

- **Command not found**: Ensure your virtual environment is activated (`source .venv/bin/activate`).
- **ModuleNotFoundError**: If running from source, ensure you installed with `pip install -e .`.
- **Permissions**: Grant Full Disk Access to your terminal or python executable if accessing protected folders (like `~/Library/Containers`).
- **Docker**: Ensure Docker Desktop is running. If file changes aren't detected, try restarting the container.
