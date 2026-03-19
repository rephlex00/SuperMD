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
from sncloud.exceptions import AuthenticationError
from sncloud.models import Directory, File

OTP_FILE = Path("/otp/code")


def read_secret(name: str) -> str:
    """Read a Docker secret from /run/secrets/<name>."""
    path = Path(f"/run/secrets/{name}")
    if not path.exists():
        print(f"[sncloud] ERROR: secret '{name}' not found at {path}", flush=True)
        sys.exit(1)
    return path.read_text().strip()


def wait_for_otp() -> str:
    """Wait for the user to write an OTP code to /otp/code."""
    print("[sncloud] Waiting for verification code...", flush=True)
    print("[sncloud] Provide the code from your email with:", flush=True)
    print("[sncloud]   docker compose exec supernote-sync sh -c 'echo 123456 > /otp/code'", flush=True)
    print("[sncloud]   (replace 123456 with your actual code)", flush=True)

    OTP_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Clear any stale OTP file
    if OTP_FILE.exists():
        OTP_FILE.unlink()

    while True:
        if OTP_FILE.exists():
            code = OTP_FILE.read_text().strip()
            if code:
                OTP_FILE.unlink(missing_ok=True)
                return code
        time.sleep(2)


def login_with_otp(client: SNClient, email: str, password: str) -> bool:
    """Handle login including E1760 OTP verification flow.

    Returns True on success, False on failure.
    """
    try:
        client.login(email, password)
        return True
    except AuthenticationError as e:
        err = str(e)
        if not err.startswith("__E1760__:"):
            print(f"[sncloud] Login failed: {e}", flush=True)
            return False

        # E1760: identity verification required — drive OTP flow
        timestamp = err.split(":", 1)[1]
        print("[sncloud] Identity verification required (new device).", flush=True)
        print("[sncloud] Sending verification code to your email...", flush=True)

        try:
            valid_code_key = client.send_verification_code(email, timestamp)
        except Exception as send_err:
            print(f"[sncloud] Could not send verification code: {send_err}", flush=True)
            print("[sncloud] A code may already have been sent. Check your email.", flush=True)
            # Still wait for the OTP — code may have been sent by a prior attempt
            valid_code_key = ""

        otp = wait_for_otp()
        print("[sncloud] Received OTP, verifying...", flush=True)

        try:
            token = client.verify_otp(email, otp, valid_code_key, timestamp)
            client._access_token = token
            print("[sncloud] Verification successful!", flush=True)
            return True
        except AuthenticationError as verify_err:
            err_str = str(verify_err)
            if err_str.startswith("__E1760__:"):
                print("[sncloud] OTP expired or invalid. Restart the container to try again.", flush=True)
                return False
            print(f"[sncloud] Verification failed: {verify_err}", flush=True)
            return False
    except Exception as e:
        print(f"[sncloud] Login failed: {e}", flush=True)
        return False


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


def read_optional_secret(name: str) -> str:
    """Read a Docker secret, returning empty string if missing or empty."""
    path = Path(f"/run/secrets/{name}")
    if path.exists():
        return path.read_text().strip()
    return ""


def main() -> None:
    email = read_secret("supernote_email")
    password = read_secret("supernote_password")
    token = read_optional_secret("supernote_token")
    sync_path = os.environ.get("SYNC_PATH", "/Note")
    interval = int(os.environ.get("SYNC_INTERVAL", "300"))
    output = Path("/notes")
    output.mkdir(parents=True, exist_ok=True)

    auth_method = "saved token" if token else "email/password"
    print("[sncloud] ════════════════════════════════════════════", flush=True)
    print("[sncloud]  Supernote Cloud Sync", flush=True)
    print(f"[sncloud]  Account:   {email}", flush=True)
    print(f"[sncloud]  Auth:      {auth_method}", flush=True)
    print(f"[sncloud]  Remote:    {sync_path}", flush=True)
    print(f"[sncloud]  Local:     {output}", flush=True)
    print(f"[sncloud]  Interval:  {interval}s", flush=True)
    print("[sncloud] ════════════════════════════════════════════", flush=True)

    client = SNClient()

    # If a saved token exists (e.g. from setup.sh OTP verification), use it directly.
    if token:
        client._access_token = token
        print(f"[sncloud] Using saved access token for {email}", flush=True)
    elif login_with_otp(client, email, password):
        print(f"[sncloud] Logged in as {email}", flush=True)
    else:
        print("[sncloud] Login failed. Will keep retrying in the sync loop.", flush=True)

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
            if login_with_otp(client, email, password):
                print("[sncloud] Re-authenticated after error", flush=True)
            else:
                print("[sncloud] Re-login failed", flush=True)

        time.sleep(interval)


if __name__ == "__main__":
    main()
