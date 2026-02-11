import base64
import os
import posixpath
from datetime import datetime
from sn2md.types import Config
from sn2md.supernotelib import Notebook
from sn2md.importers.note import convert_binary_to_image
from sn2md.ai_utils import image_to_text
import re

from sn2md.date_utils import format_date

def create_basic_context(file_basename: str, file_name: str) -> dict:
    # Try to parse date from filename (YYYYMMDD_HHMMSS or YYYYMMDD)
    # This is more reliable than filesystem ctime over sync
    match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{6})", file_basename)
    if not match:
        match = re.search(r"(\d{4})(\d{2})(\d{2})", file_basename)
        
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3)
        # Construct a datetime from the filename
        try:
             created_at = datetime(int(year), int(month), int(day))
        except ValueError:
             # Fallback if invalid date like 20261332
             created_at = datetime.fromtimestamp(os.path.getmtime(file_name))
    else:
        # Fallback to mtime (usually preserved by sync)
        created_at = datetime.fromtimestamp(os.path.getmtime(file_name))

    return {
        "file_basename": file_basename,
        "file_name": file_name,
        "ctime": created_at,
        "mtime": datetime.fromtimestamp(os.path.getmtime(file_name)),
        "year_month_day": created_at.strftime("%Y-%m-%d"),
        "year": created_at.strftime("%Y"),
        "month": created_at.strftime("%b"),
        "day": created_at.strftime("%d"),
        "format_date": lambda fmt: format_date(created_at, fmt), # Custom helper
    }

def create_notebook_context(notebook: Notebook, config: Config, model: str) -> dict:
    def get_link_str(type_code: int) -> str:
        if type_code == 0:
            return "page"
        elif type_code == 1:
            return "file"
        elif type_code == 2:
            return "web"
        return "unknown"

    def get_inout_str(type_code: int) -> str:
        if type_code == 0:
            return "out"
        elif type_code == 1:
            return "in"
        return "unknown"

    return {
        "links": [
            {
                "page_number": link.get_page_number(),
                "type": get_link_str(link.get_type()),
                "name": os.path.basename(
                    base64.standard_b64decode(link.get_filepath())
                ).decode("utf-8"),
                "device_path": base64.standard_b64decode(link.get_filepath()),
                "inout": get_inout_str(link.get_inout()),
            }
            for link in (notebook.links if notebook else [])
        ],
        "keywords": [
            {
                "page_number": keyword.get_page_number(),
                "content": keyword.get_content().decode("utf-8"),
            }
            for keyword in (notebook.keywords if notebook else [])
        ],
        "titles": [
            {
                "page_number": title.get_page_number(),
                "content": image_to_text(
                    convert_binary_to_image(notebook, title),
                    config.api_key,
                    model,
                    config.title_prompt,
                ),
                "level": title.metadata["TITLELEVEL"],
            }
            for title in (notebook.titles if notebook else [])
        ],
    }


def create_context(
    notebook: Notebook | None,
    pngs: list[str],
    config: Config,
    file_name: str,
    model: str,
    template_output: str,
    basic_context: dict,
) -> dict:
    images = []
    for png_path in pngs:
        image_name = os.path.basename(png_path)
        relative_link = posixpath.join("attachments", image_name)
        images.append(
            {
                "name": image_name,
                "rel_path": relative_link,
                "link": relative_link,
                "abs_path": os.path.abspath(png_path),
            }
        )

    context = {
        "markdown": template_output,
        "llm_output": template_output,
        "images": images,
        **basic_context,
    }

    if notebook:
        return {
            **context,
            **create_notebook_context(notebook, config, model),
        }

    return {
        **context,
        "links": [],
        "keywords": [],
        "titles": [],
    }
