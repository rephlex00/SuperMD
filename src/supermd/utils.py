
import os
import hashlib
from pathlib import Path

def shorten_path(path_str: str, levels: int = 3) -> str:
    try:
        p = Path(path_str)
        parts = p.parts
        if len(parts) > levels:
            return "..." + os.sep + os.path.join(*parts[-levels:])
    except Exception:
        pass
    return path_str

def compute_file_hash(filepath: str) -> str:
    """Compute SHA1 hash of a file."""
    sha1 = hashlib.sha1()
    with open(filepath, 'rb') as f:
        while True:
            data = f.read(65536)
            if not data:
                break
            sha1.update(data)
    return sha1.hexdigest()
