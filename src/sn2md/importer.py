import base64
from typing import Generator
import uuid
import shutil
import logging
import os
import posixpath
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path

from sn2md.utils import shorten_path


from jinja2 import Template
from sn2md.supernotelib import Notebook

from sn2md.ai_utils import image_to_markdown, image_to_text
from sn2md.importers.atelier import AtelierExtractor
from sn2md.importers.pdf import PDFExtractor
from sn2md.importers.png import PNGExtractor
from sn2md.types import Config, ImageExtractor
from sn2md.importers.note import NotebookExtractor, convert_binary_to_image
from sn2md.metadata import (
    check_metadata_file, 
    write_metadata_file,
    InputNotChangedError,
    OutputChangedError
)

from tqdm import tqdm
import click

logger = logging.getLogger(__name__)




@contextmanager
def generate_images(
    image_extractor: ImageExtractor, file_name: str, output: str
) -> Generator[list[str], None, None]:
    image_output_path = os.path.join(output, uuid.uuid4().hex)
    os.makedirs(image_output_path, exist_ok=True)

    logger.debug("Storing images in %s", shorten_path(image_output_path))

    try:
        yield image_extractor.extract_images(file_name, image_output_path)
    finally:
        shutil.rmtree(image_output_path)


def process_pages(
    pngs: list[str],
    config: Config,
    model: str,
    progress: bool,
    prompt_context: dict | None = None,
) -> str:
    page_list = tqdm(pngs, desc="Processing pages", unit="page") if progress else pngs

    template_output = ""
    for i, page in enumerate(page_list):
        context = ""
        if i > 0 and len(template_output) > 0:
            # include the last 50 characters...for continuity of the transcription:
            context = template_output[-50:]
        try:
            template_output = (
                template_output
                + "\n"
                + image_to_markdown(
                    page,
                    context,
                    config.api_key,
                    model,
                    config.prompt,
                    prompt_context,
                )
            )
        except KeyError as e:
            logger.error(f"Template rendering failed. Missing key: {e}")
            if prompt_context:
                logger.error(f"Available context keys: {list(prompt_context.keys())}")
            else:
                logger.error("Prompt context is None!")
            raise
    return template_output


def create_basic_context(file_basename: str, file_name: str) -> dict:
    import re
    
    # Try to parse date from filename (YYYYMMDD_HHMMSS or YYYYMMDD)
    # This is more reliable than filesystem ctime over sync
    match = re.search(r"(\d{4})(\d{2})(\d{2})_(\d{6})", file_basename)
    if not match:
        match = re.search(r"(\d{4})(\d{2})(\d{2})", file_basename)
        
    if match:
        year, month, day = match.group(1), match.group(2), match.group(3)
        # Construct a datetime from the filename
        # Default to noon if no time provided, to avoid timezone edge cases?
        # Actually just need a valid datetime object for strftime below
        try:
             created_at = datetime(int(year), int(month), int(day))
        except ValueError:
             # Fallback if invalid date like 20261332
             created_at = datetime.fromtimestamp(os.path.getmtime(file_name))
    else:
        # Fallback to mtime (usually preserved by sync)
        # ctime is unreliable on Docker/Linux transfers
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
    }

def create_notebook_context(notebook: Notebook, config: Config, model: str) -> dict:
    # Codes:
    # TODO add a pull request for this feature:
    # https://github.com/jya-dev/supernote-tool/blob/807d5fa4bf524fdb1f9c7f1c67ed66ea96a49db5/supernotelib/fileformat.py#L236
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

    # TODO add pages - for each page include keywords and titles
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


def generate_output(
    pngs: list[str],
    config: Config,
    context: dict,
    file_name: str,
    output: str,
    template,
) -> None:
    jinja_markdown = template.render(context)

    for image in context.get("images", []):
        image_name = image.get("name")
        image_link = image.get("link") or posixpath.join("attachments", image_name)
        if image_name:
            needle = f"]({image_name})"
            replacement = f"]({image_link})"
            if needle in jinja_markdown and replacement not in jinja_markdown:
                jinja_markdown = jinja_markdown.replace(needle, replacement)

    output_filename_template = Template(config.output_filename_template)
    output_filename = output_filename_template.render(context)

    output_path_template = Template(config.output_path_template)
    output_path = output_path_template.render(context)
    output_path = os.path.join(output, output_path)
    os.makedirs(output_path, exist_ok=True)
    image_output_dir = os.path.join(output_path, "attachments")
    os.makedirs(image_output_dir, exist_ok=True)

    output_path_and_file = os.path.join(output_path, output_filename)
    with open(output_path_and_file, "w") as f:
        _ = f.write(jinja_markdown)
    logger.debug("Wrote output to %s", shorten_path(output_path_and_file))

    # move everything from image_output_path to the dedicated image folder:
    for png_path in pngs:
        png_name = os.path.basename(png_path)
        destination = os.path.join(image_output_dir, png_name)
        os.rename(png_path, destination)

    metadata_dir = os.path.join(output_path, ".meta")
    write_metadata_file(metadata_dir, file_name, output_path_and_file)

    logger.debug("Moved images to %s", shorten_path(image_output_dir))

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    import click
    msg = f"[{timestamp}] Generated: {output_path_and_file}"
    tqdm.write(click.style(msg, fg="green"))


def verify_metadata_file(config: Config, output: str, file_name: str, dry_run: bool = False) -> None:
    file_basename = os.path.splitext(os.path.basename(file_name))[0]
    basic_context = create_basic_context(file_basename, file_name)

    output_path_template = Template(config.output_path_template)
    output_path = output_path_template.render(basic_context)
    output_path = os.path.join(output, output_path)

    metadata_dir = os.path.join(output_path, ".meta")
    logger.info(f"Checking metadata for {file_basename} in {metadata_dir}")
    check_metadata_file(metadata_dir, file_name, dry_run=dry_run)


def import_supernote_file_core(
    image_extractor: ImageExtractor,
    file_name: str,
    output: str,
    config: Config,
    force: bool = False,
    progress: bool = False,
    model: str | None = None,
    dry_run: bool = False,
) -> None:
    logger.debug("import_supernote_file_core: %s", shorten_path(file_name))
    
    # Verification (raises exception if unchanged/locked)
    if not force:
        verify_metadata_file(config, output, file_name, dry_run=dry_run)

    if dry_run:
        import click
        tqdm.write(click.style(f"[dry-run] Would process {shorten_path(file_name)}", fg="green"))
        return

    model = model if model else config.model
    template = Template(config.template)
    file_basename = os.path.splitext(os.path.basename(file_name))[0]
    basic_context = create_basic_context(file_basename, file_name)

    with generate_images(image_extractor, file_name, output) as pngs:
        template_output = process_pages(
            pngs,
            config,
            model,
            progress,
            basic_context,
        )

        notebook = image_extractor.get_notebook(file_name)
        context = create_context(
            notebook,
            pngs,
            config,
            file_name,
            model,
            template_output,
            basic_context,
        )

        generate_output(pngs, config, context, file_name, output, template)


def import_supernote_directory_core(
    directory: str,
    output: str,
    config: Config,
    force: bool = False,
    progress: bool = False,
    model: str | None = None,
    dry_run: bool = False,
) -> None:
    for root, _, files in os.walk(directory):
        file_list = (
            tqdm(files, desc="Processing files", unit="file") if progress else files
        )
        for file in file_list:
            filename = os.path.join(root, file)
            logger.debug(f"Scanning file: {shorten_path(filename)}")
            try:
                if file.lower().endswith(".note"):
                    import_supernote_file_core(
                        NotebookExtractor(),
                        filename,
                        output,
                        config,
                        force,
                        progress,
                        model,
                        dry_run
                    )
                if file.lower().endswith(".pdf"):
                    import_supernote_file_core(
                        PDFExtractor(), filename, output, config, force, progress, model, dry_run
                    )
                if file.lower().endswith(".png"):
                    import_supernote_file_core(
                        PNGExtractor(), filename, output, config, force, progress, model, dry_run
                    )
                if file.lower().endswith(".spd"):
                    import_supernote_file_core(
                        AtelierExtractor(),
                        filename,
                        output,
                        config,
                        force,
                        progress,
                        model,
                        dry_run
                    )
            except InputNotChangedError:
                if dry_run:
                     import click
                     tqdm.write(click.style(f"[dry-run] Would skip {shorten_path(filename)} (Unchanged)", fg="yellow"))
                else:
                     logger.debug(f"Skipping {shorten_path(filename)}: Input not changed")
            except OutputChangedError as e:
                import click
                if dry_run:
                     tqdm.write(click.style(f"[dry-run] Would skip {shorten_path(filename)} (Output modified)", fg="red"))
                else:
                     tqdm.write(click.style(f"Refusing to update {shorten_path(filename)}: Output file has been modified locally. Use --force to overwrite.", fg="yellow"))
                     logger.warning(f"Skipping {shorten_path(filename)}: {e}")
            except ValueError as e:
                logger.exception(f"Skipping {shorten_path(filename)}: {e}")


def rebuild_metadata_for_file(file_name: str, config: Config, output_dir: str, dry_run: bool = False) -> None:
    logger.debug(f"Rebuild check for {shorten_path(file_name)}")
    
    file_basename = os.path.splitext(os.path.basename(file_name))[0]
    basic_context = create_basic_context(file_basename, file_name)
    
    # Calculate where the output should be
    output_path_template = Template(config.output_path_template)
    rel_output_path = output_path_template.render(basic_context)
    full_output_dir = os.path.join(output_dir, rel_output_path)
    
    # Calculate filename
    output_filename_template = Template(config.output_filename_template)
    try:
        output_filename = output_filename_template.render({**basic_context, "images": []})
    except Exception:
        output_filename = f"{file_basename}.md"

    output_file_path = os.path.join(full_output_dir, output_filename)
    
    # Debug logging for troubleshooting path issues
    # logger.debug(f"Checking for existing output: {shorten_path(output_file_path)}")
    
    if os.path.exists(output_file_path):
        if dry_run:
            tqdm.write(click.style(f"[dry-run] Would rebuild meta for {shorten_path(file_name)} -> {shorten_path(output_file_path)}", fg="green"))
        else:
            metadata_dir = os.path.join(full_output_dir, ".meta")
            tqdm.write(click.style(f"Rebuilding meta for {shorten_path(file_name)}", fg="green"))
            write_metadata_file(metadata_dir, file_name, output_file_path)
    else:
        # Output main file doesn't exist
        if dry_run: 
             tqdm.write(click.style(f"[dry-run] Output not found for {shorten_path(file_name)}: expected {shorten_path(output_file_path)}", fg="blue"))
        # pass


def rebuild_metadata_directory(
    directory: str,
    output: str,
    config: Config,
    dry_run: bool = False
) -> None:
    for root, _, files in os.walk(directory):
        file_list = tqdm(files, desc="Rebuilding Metadata", unit="file")
        for file in file_list:
             filename = os.path.join(root, file)
             if file.lower().endswith(".note") or file.lower().endswith(".pdf") or file.lower().endswith(".png") or file.lower().endswith(".spd"):
                 rebuild_metadata_for_file(filename, config, output, dry_run=dry_run)

def clean_metadata_directory(directory: str, dry_run: bool = False) -> None:
    import shutil
    import click
    
    deleted_count = 0
    candidate_dirs = []
    
    # First pass: collect all .meta directories
    for root, dirs, _ in os.walk(directory):
        if ".meta" in dirs:
            meta_path = os.path.join(root, ".meta")
            candidate_dirs.append(meta_path)
            
    if not candidate_dirs:
        logger.info(f"No .meta directories found in {directory}")
        return

    logger.info(f"Found {len(candidate_dirs)} .meta directories to clean in {directory}")
    
    for meta_path in candidate_dirs:
        if dry_run:
            tqdm.write(click.style(f"[dry-run] Would delete: {shorten_path(meta_path)}", fg="red"))
        else:
            try:
                shutil.rmtree(meta_path)
                tqdm.write(click.style(f"Deleted: {shorten_path(meta_path)}", fg="red"))
                deleted_count += 1
            except Exception as e:
                logger.error(f"Failed to delete {meta_path}: {e}")
                
    if not dry_run:
        logger.info(f"Cleaned {deleted_count} directories.")
