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

1. Install [uv](https://docs.astral.sh/uv/) if you haven't already.

2. Sync the project (installs dependencies and creates `.venv`):
   ```bash
   uv sync
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
# Or with uv:
uv run sn2md-cli run
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
   docker-compose logs -f
   ```

5. **Permission Management (Linux)**:
   If you encounter permission issues on Linux, you can set the `PUID` and `PGID` environment variables to match your host user's IDs (usually 1000).
   In `docker-compose.yml`:
   ```yaml
   environment:
     - PUID=1000
     - PGID=1000
   ```

## Supernote Private Cloud Integration

You can run `sn2md` alongside the official **Supernote Private Cloud** containers. This allows you to sync your files directly from your Supernote device to your self-hosted cloud, where they will be automatically picked up and converted by `sn2md`.

For detailed setup instructions, including SSL configuration and Obsidian auto-sync, see the dedicated documentation:
👉 **[Supernote Private Cloud Setup Guide](README.sn-cloud.md)**

## Troubleshooting

- **Command not found**: Ensure you run commands with `uv run` or activate the environment.
- **ModuleNotFoundError**: Run `uv sync` to ensure dependencies are installed.
- **Permissions**: Grant Full Disk Access to your terminal or python executable if accessing protected folders (like `~/Library/Containers`).
- **Docker**: Ensure Docker Desktop is running. If file changes aren't detected, try restarting the container.
