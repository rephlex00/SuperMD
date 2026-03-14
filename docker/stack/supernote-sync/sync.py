"""Supernote Cloud → local filesystem sync.

Periodically downloads .note files from Supernote Cloud to /notes.
Credentials are read from Docker secrets at /run/secrets/.
"""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path, PurePosixPath

from sncloud import SNClient
from sncloud.models import Directory, File


def read_secret(name: str) -> str:
    """Read a Docker secret from /run/secrets/<name>."""
    path = Path(f"/run/secrets/{name}")
    if not path.exists():
        print(f"[sncloud] ERROR: secret '{name}' not found at {path}", flush=True)
        sys.exit(1)
    return path.read_text().strip()


def sync_directory(
    client: SNClient,
    remote_path: str,
    local_root: Path,
    extensions: tuple[str, ...] = (".note", ".spd"),
) -> int:
    """Recursively sync files from a remote directory.

    Returns the number of files downloaded.
    """
    downloaded = 0

    try:
        items = client.ls(remote_path)
    except Exception as e:
        print(f"[sncloud] ERROR listing {remote_path}: {e}", flush=True)
        return 0

    for item in items:
        if isinstance(item, Directory):
            child_remote = f"{remote_path}/{item.file_name}"
            child_local = local_root / item.file_name
            child_local.mkdir(parents=True, exist_ok=True)
            downloaded += sync_directory(client, child_remote, child_local, extensions)

        elif isinstance(item, File):
            if not item.file_name.lower().endswith(extensions):
                continue

            # Path traversal guard: reject filenames containing separators or
            # dot-prefixed names that could escape the output directory.
            if (
                "/" in item.file_name
                or "\\" in item.file_name
                or item.file_name.startswith(".")
                or item.file_name != PurePosixPath(item.file_name).name
            ):
                print(
                    f"[sncloud] WARNING: Skipping suspicious filename: {item.file_name!r}",
                    flush=True,
                )
                continue

            local_file = local_root / item.file_name

            # Skip if already downloaded.
            if local_file.exists():
                continue

            print(f"[sncloud] Downloading {remote_path}/{item.file_name}", flush=True)
            tmp_dir: Path | None = None
            try:
                # Download to a temporary directory, then atomically rename into
                # place.  This prevents SuperMD from processing a partially-written
                # file (sncloud.get() writes to <path>/<file_name> directly).
                tmp_dir = Path(tempfile.mkdtemp(dir=local_root))
                client.get(f"{remote_path}/{item.file_name}", tmp_dir)
                tmp_file = tmp_dir / item.file_name
                tmp_file.rename(local_file)
                downloaded += 1

            except Exception as e:
                print(
                    f"[sncloud] ERROR downloading {item.file_name}: {e}", flush=True
                )
            finally:
                if tmp_dir is not None and tmp_dir.exists():
                    shutil.rmtree(tmp_dir, ignore_errors=True)

    return downloaded


def main() -> None:
    email = read_secret("supernote_email")
    password = read_secret("supernote_password")
    sync_path = os.environ.get("SYNC_PATH", "/Note")
    interval = int(os.environ.get("SYNC_INTERVAL", "300"))
    output = Path("/notes")
    output.mkdir(parents=True, exist_ok=True)

    client = SNClient()
    client.login(email, password)
    print(f"[sncloud] Logged in as {email}", flush=True)

    while True:
        try:
            count = sync_directory(client, sync_path, output)
            if count:
                print(f"[sncloud] Downloaded {count} file(s)", flush=True)
            print(
                f"[sncloud] Sync complete, next check in {interval}s", flush=True
            )
        except Exception as e:
            print(f"[sncloud] ERROR during sync: {e}", flush=True)
            # Re-login in case the session expired.
            try:
                client.login(email, password)
                print("[sncloud] Re-authenticated after error", flush=True)
            except Exception as login_err:
                print(f"[sncloud] Re-login failed: {login_err}", flush=True)

        time.sleep(interval)


if __name__ == "__main__":
    main()
