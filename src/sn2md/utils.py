
import os
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
