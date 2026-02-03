
import logging
import sys
import re
from datetime import datetime
import click
from tqdm import tqdm

logger = logging.getLogger("sn2md")

class Console:
    def __init__(self):
        self.debug_mode = False
        self._setup_logging()

    def _setup_logging(self):
        # We want to capture everything, but only show what we want in our console
        # So we configure the root logger to catch everything, but our handlers will decide format
        root_logger = logging.getLogger()
        root_logger.setLevel(logging.INFO)
        
        # Remove existing handlers to avoid duplication if re-initializing
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)

        # Create a handler that writes to tqdm.write (stderr/stdout safe)
        # But we will do manual formatting in our log method mainly.
        # However, for library logs (like urllib), we might want a standard handler.
        # For now, let's keep it simple: our tool uses explicit console.log
        pass

    def set_level(self, level: str | int):
        if isinstance(level, str):
            level = level.upper()
        
        root_logger = logging.getLogger()
        root_logger.setLevel(level)
        self.debug_mode = (level == "DEBUG" or level == logging.DEBUG)

    def log(self, msg: str, fg: str = None, bold: bool = False):
        """
        Log a message to the console with consistent formatting.
        Uses tqdm.write to play nice with progress bars.
        """
        ts = datetime.now().strftime("%H:%M:%S")
        ts_prefix = f"[{ts}]"
        ts_colored = click.style(ts_prefix, fg="bright_black")
        
        # Calculate indent for subsequent lines (timestamp length + 1 space)
        indent_len = len(ts_prefix) + 1
        indent_str = " " * indent_len

        if fg:
            # Explicit color override
            lines = msg.splitlines()
            first = lines[0]
            tqdm.write(f"{ts_colored} {click.style(first, fg=fg, bold=bold)}")
            for line in lines[1:]:
                tqdm.write(f"{indent_str}{click.style(line, fg=fg)}")
            return

        # 1. Parse Tag/Level from first line if present
        # Common patterns: [dry-run], [job ...], [WARNING], [ERROR]
        lines = msg.splitlines()
        first_line = lines[0]
        
        tag_match = re.match(r"^(\[[^\]]+\])\s*(.*)$", first_line)
        tag_colored = ""
        body_str = first_line
        tag_sub_indent = ""

        if tag_match:
            tag_str = tag_match.group(1)
            body_str = tag_match.group(2)
            tag_sub_indent = " " * (len(tag_str) + 1)
            
            # Color tag based on content
            lower_tag = tag_str.lower()
            if "dry-run" in lower_tag:
                tag_colored = click.style(tag_str, fg="cyan")
            elif "job" in lower_tag or "watch" in lower_tag:
                tag_colored = click.style(tag_str, fg="blue")
            elif "error" in lower_tag or "fail" in lower_tag:
                 tag_colored = click.style(tag_str, fg="red", bold=True)
            elif "warn" in lower_tag:
                 tag_colored = click.style(tag_str, fg="yellow", bold=True)
            elif "success" in lower_tag:
                 tag_colored = click.style(tag_str, fg="green", bold=True)
            else:
                tag_colored = click.style(tag_str, fg="magenta")
        
        # Helper to style body content
        def style_body(text):
            res = text
            # Auto-highlight keywords
            if "SUCCESS" in text:
                 res = text.replace("SUCCESS", click.style("SUCCESS", fg="green", bold=True))
            elif "FAILED" in text:
                 res = text.replace("FAILED", click.style("FAILED", fg="red", bold=True))
            elif "Error:" in text:
                 res = text.replace("Error:", click.style("Error:", fg="red", bold=True))
            
            # Highlight paths (roughly)
            # Regex for paths is hard, but we can look for key-value pairs
            kv_match = re.match(r"^([A-Za-z0-9 _-]+):\s+(.*)$", text)
            if kv_match:
                label = kv_match.group(1)
                value = kv_match.group(2)
                label_colored = click.style(f"{label}:", fg="bright_black")
                
                if value.startswith("/") or value.startswith("~") or "directory" in value:
                     value_colored = click.style(value, fg="yellow")
                else:
                     value_colored = value
                res = f"{label_colored} {value_colored}"
            
            return res

        body_colored = style_body(body_str)
        
        if tag_colored:
            tqdm.write(f"{ts_colored} {tag_colored} {body_colored}")
        else:
            tqdm.write(f"{ts_colored} {body_colored}")
            
        full_indent = indent_str + tag_sub_indent
        
        for line in lines[1:]:
            stripped = line.strip()
            styled_line = line
            if stripped.startswith("-") or stripped.startswith("/"):
                # It's an arg or path list usually
                styled_line = click.style(line, fg="yellow")
            elif "Error" in stripped:
                 styled_line = click.style(line, fg="red")
            
            tqdm.write(f"{full_indent}{styled_line}")

    def debug(self, msg: str):
        if self.debug_mode:
            self.log(f"[DEBUG] {msg}", fg="bright_black")
    
    def info(self, msg: str):
        self.log(msg)
    
    def warning(self, msg: str):
        self.log(f"[WARNING] {msg}")

    def error(self, msg: str):
        self.log(f"[ERROR] {msg}")
        
    def success(self, msg: str):
        self.log(msg, fg="green")

# Global instance
console = Console()
