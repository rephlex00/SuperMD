import uuid
import shutil
import os
import posixpath
import json
from typing import Generator
from time import sleep, monotonic
from contextlib import contextmanager
from datetime import datetime
from jinja2 import Template
from tqdm import tqdm

from supermd.types import ImageExtractor
from supermd.config import SuperMDConfig
from supermd.importers import get_extractor, SUPPORTED_EXTENSIONS
from supermd.ai_utils import image_to_markdown
from supermd.utils import shorten_path, compute_file_hash
from supermd.metadata_db import (
    MetadataManager,
    InputNotChangedError,
    OutputChangedError
)
from supermd.context import create_basic_context, create_context
from supermd.date_utils import expand_date_tokens
from supermd.console import console


class CooldownState:
    """Enforces a minimum delay between consecutive API calls."""

    def __init__(self, cooldown: float):
        self.cooldown = cooldown
        self._last_call: float | None = None

    def wait(self, progress_bar=None) -> None:
        if self.cooldown <= 0 or self._last_call is None:
            return
        step = 0.1
        remaining = self.cooldown - (monotonic() - self._last_call)
        while remaining > 0:
            if progress_bar:
                progress_bar.set_description(f"Cooldown: {remaining:.1f}s")
            sleep(step)
            remaining -= step

    def mark(self) -> None:
        self._last_call = monotonic()


@contextmanager
def generate_images(
    image_extractor: ImageExtractor, file_name: str, output: str
) -> Generator[list[str], None, None]:
    image_output_path = os.path.join(output, uuid.uuid4().hex)
    os.makedirs(image_output_path, exist_ok=True)

    console.debug(f"Storing images in {shorten_path(image_output_path)}")

    try:
        yield image_extractor.extract_images(file_name, image_output_path)
    finally:
        shutil.rmtree(image_output_path)


def process_pages(
    pngs: list[str],
    config: SuperMDConfig,
    model: str,
    progress_bar: tqdm | None = None,
    prompt_context: dict | None = None,
    cooldown_state: CooldownState | None = None,
) -> str:
    template_output = ""
    total_pages = len(pngs)

    for i, page in enumerate(pngs):
        # Update progress description
        if progress_bar:
             progress_bar.set_description(f"Processing Page {i+1}/{total_pages}")

        # Enforce cooldown before every API call (skips wait on the very first call ever)
        if cooldown_state:
            cooldown_state.wait(progress_bar)
            if progress_bar:
                progress_bar.set_description(f"Processing Page {i+1}/{total_pages}")

        context = ""
        if i > 0 and len(template_output) > 0:
            # include the last 50 characters...for continuity of the transcription
            context = template_output[-50:]
        try:
            template_output = (
                template_output
                + "\n"
                + image_to_markdown(
                    page,
                    context,
                    model,
                    config.prompt,
                    prompt_context,
                )
            )
            if cooldown_state:
                cooldown_state.mark()
        except KeyError as e:
            console.error(f"Template rendering failed. Missing key: {e}")
            if prompt_context:
                console.error(f"Available context keys: {list(prompt_context.keys())}")
            else:
                console.error("Prompt context is None!")
            raise
    return template_output


def generate_output(
    pngs: list[str],
    config: SuperMDConfig,
    context: dict,
    file_name: str,
    output: str,
    template,
    metadata_manager: MetadataManager,
    input_hash: str,
) -> None:
    ctime = context.get("ctime")

    def preprocess(s: str) -> str:
        return expand_date_tokens(s, ctime) if ctime else s

    jinja_markdown = template.render(context)

    for image in context.get("images", []):
        image_name = image.get("name")
        image_link = image.get("link") or posixpath.join("attachments", image_name)
        if image_name:
            needle = f"]({image_name})"
            replacement = f"]({image_link})"
            if needle in jinja_markdown and replacement not in jinja_markdown:
                jinja_markdown = jinja_markdown.replace(needle, replacement)

    output_filename_template = Template(preprocess(config.output_filename_template))
    output_filename = output_filename_template.render(context)

    output_path_template = Template(preprocess(config.output_path_template))
    output_path = output_path_template.render(context)
    output_path = os.path.join(output, output_path)
    os.makedirs(output_path, exist_ok=True)
    image_output_dir = os.path.join(output_path, "attachments")
    os.makedirs(image_output_dir, exist_ok=True)

    output_path_and_file = os.path.join(output_path, output_filename)
    with open(output_path_and_file, "w") as f:
        _ = f.write(jinja_markdown)
    console.debug(f"Wrote output to {shorten_path(output_path_and_file)}")

    # Preserve file creation date
    if "ctime" in context:
        try:
            timestamp = context["ctime"].timestamp()
            os.utime(output_path_and_file, (timestamp, timestamp))
            console.debug(f"Restored timestamp to {context['ctime']}")
        except Exception as e:
            console.warning(f"Failed to restore timestamp: {e}")

    # move everything from image_output_path to the dedicated image folder:
    image_files = []
    for png_path in pngs:
        png_name = os.path.basename(png_path)
        destination = os.path.join(image_output_dir, png_name)
        shutil.move(png_path, destination)
        image_files.append(png_name)

    console.debug(f"Moved images to {shorten_path(image_output_dir)}")

    # Update metadata
    output_hash = compute_file_hash(output_path_and_file)
    
    output_path_template_original = Template(preprocess(config.output_path_template))
    rel_path_dir = output_path_template_original.render(context)
    expected_rel_path = os.path.join(rel_path_dir, output_filename)

    metadata_manager.upsert_entry(
        input_note_filename=os.path.basename(file_name),
        output_markdown_filename=output_filename,
        expected_path=expected_rel_path,
        actual_file_path=output_path_and_file,
        input_file_hash=input_hash,
        output_file_hash=output_hash,
        is_locked=False,
        image_files=json.dumps(image_files)
    )

    note_ctime = ""
    if "ctime" in context:
        # Format as YYYY-MM-DD
        note_ctime = f" (Created: {context['ctime'].strftime('%Y-%m-%d')})"

    msg = f"Generated: {output_path_and_file}{note_ctime}"
    console.log(msg, fg="green")


def verify_metadata_file(
    metadata_manager: MetadataManager,
    file_name: str,
    input_hash: str,
    dry_run: bool = False
) -> None:
    file_basename = os.path.basename(file_name)
    entry = metadata_manager.get_entry_by_input(file_basename)
    
    if not entry:
        return # New file

    # 1. Check if output is missing (Broken link) -> Reprocess
    if not entry.actual_file_path or not os.path.exists(entry.actual_file_path):
        if dry_run:
             console.log(f"  [dry-run] Output file missing for {file_basename}", fg="blue")
        else:
             console.info(f"Output file missing for {file_basename}, forcing reprocessing.")
        return 

    # 2. Check if input has changed
    if entry.input_file_hash == input_hash:
        raise InputNotChangedError(f"Input {shorten_path(file_name)} has NOT changed!") 

    # Check if output has changed
    current_output_hash = compute_file_hash(entry.actual_file_path)
    if entry.output_file_hash == current_output_hash:
        return # Output safe to overwrite

    # Output changed, check for ignoreSNLock
    try:
        with open(entry.actual_file_path, "r", encoding="utf-8", errors="ignore") as f:
            content = f.read()
            import re
            if re.search(r"^ignoresnlock:\s*true", content, re.MULTILINE | re.IGNORECASE):
                return # User opted out
    except Exception:
        pass

    raise OutputChangedError(f"Output {shorten_path(entry.actual_file_path)} HAS been changed!")


def convert_file(
    image_extractor: ImageExtractor,
    file_name: str,
    output: str,
    config: SuperMDConfig,
    force: bool = False,
    progress_bar: tqdm | None = None,
    model: str | None = None,
    dry_run: bool = False,
    metadata_manager: MetadataManager | None = None,
    cooldown: float = 0.0,
    _cooldown_state: CooldownState | None = None,
) -> None:
    console.debug(f"convert_file: {shorten_path(file_name)}")
    
    if progress_bar:
        progress_bar.set_description(f"Processing {shorten_path(file_name)}")
    
    should_close_manager = False
    if metadata_manager is None:
        metadata_manager = MetadataManager(output)
        should_close_manager = True

    try:
        if not os.path.exists(file_name):
            console.error(f"File not found: {file_name}")
            return

        input_hash = compute_file_hash(file_name)

        # Verification (raises exception if unchanged/locked)
        if not force:
            verify_metadata_file(metadata_manager, file_name, input_hash, dry_run=dry_run)

        if dry_run:
            console.log(f"[dry-run] Would process {shorten_path(file_name)}", fg="green")
            return

        # Prepare for processing
        try:
             entry = metadata_manager.get_entry_by_input(os.path.basename(file_name))
             if entry and entry.image_files:
                 try:
                     old_images = json.loads(entry.image_files) if entry.image_files.startswith("[") else entry.image_files.split(",")
                     if entry.actual_file_path:
                         parent_dir = os.path.dirname(entry.actual_file_path)
                         attach_dir = os.path.join(parent_dir, "attachments")
                         for img in old_images:
                             img_path = os.path.join(attach_dir, img.strip())
                             if os.path.exists(img_path):
                                 os.remove(img_path)
                 except Exception as e:
                     console.warning(f"Failed to cleanup old images: {e}")
        except Exception as e:
             console.debug(f"Image cleanup skipped: {e}")

        model = model if model else config.model
        file_basename = os.path.splitext(os.path.basename(file_name))[0]
        basic_context = create_basic_context(file_basename, file_name)
        ctime = basic_context.get("ctime")
        template_str = expand_date_tokens(config.template, ctime) if ctime else config.template
        template = Template(template_str)

        cooldown_state = _cooldown_state or (CooldownState(cooldown) if cooldown > 0 else None)

        with generate_images(image_extractor, file_name, output) as pngs:
            template_output = process_pages(
                pngs,
                config,
                model,
                progress_bar,
                basic_context,
                cooldown_state=cooldown_state,
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
                cooldown_state=cooldown_state,
            )

            generate_output(
                pngs, 
                config, 
                context, 
                file_name, 
                output, 
                template,
                metadata_manager,
                input_hash
            )

    finally:
        if should_close_manager:
            metadata_manager.close()


def convert_directory(
    directory: str,
    output: str,
    config: SuperMDConfig,
    force: bool = False,
    progress: bool = False,
    model: str | None = None,
    dry_run: bool = False,
    cooldown: float = 0.0,
) -> None:
    metadata_manager = MetadataManager(output)
    cooldown_state = CooldownState(cooldown) if cooldown > 0 else None
    try:
        for root, _, files in os.walk(directory):
            # Sort files for consistent order
            files.sort()
            
            # Filter relevant files first to know count
            relevant_files = [
                f for f in files
                if f.lower().endswith(SUPPORTED_EXTENSIONS)
            ]
            
            if not relevant_files:
                continue

            file_iterator = relevant_files
            pbar = None
            
            if progress:
                pbar = tqdm(relevant_files, desc="Scanning...", unit="file")
                file_iterator = pbar

            for file in file_iterator:
                filename = os.path.join(root, file)
                console.debug(f"Scanning file: {shorten_path(filename)}")
                
                try:
                    extractor = get_extractor(file)

                    if extractor:
                        convert_file(
                            extractor,
                            filename,
                            output,
                            config,
                            force,
                            progress_bar=pbar,
                            model=model,
                            dry_run=dry_run,
                            metadata_manager=metadata_manager,
                            _cooldown_state=cooldown_state,
                        )
                except InputNotChangedError:
                    if dry_run:
                        console.log(f"[dry-run] Would skip {shorten_path(filename)} (Unchanged)", fg="yellow")
                    else:
                        console.debug(f"Skipping {shorten_path(filename)}: Input not changed")
                except OutputChangedError as e:
                    if dry_run:
                        console.log(f"[dry-run] Would skip {shorten_path(filename)} (Output modified)", fg="red")
                    else:
                        console.warning(f"Refusing to update {shorten_path(filename)}: Output modified. Use --force to overwrite. ({e})")
                except ValueError as e:
                    console.error(f"Skipping {shorten_path(filename)}: {e}")
    finally:
        metadata_manager.close()


def rebuild_metadata_for_file(
    file_name: str, 
    config: SuperMDConfig, 
    output_dir: str, 
    metadata_manager: MetadataManager,
    dry_run: bool = False
) -> None:
    console.debug(f"Rebuild check for {shorten_path(file_name)}")
    
    file_basename = os.path.splitext(os.path.basename(file_name))[0]
    basic_context = create_basic_context(file_basename, file_name)
    
    # Calculate where the output should be
    ctime = basic_context.get("ctime")
    def preprocess(s: str) -> str:
        return expand_date_tokens(s, ctime) if ctime else s

    output_path_template = Template(preprocess(config.output_path_template))
    rel_output_path = output_path_template.render(basic_context)
    full_output_dir = os.path.join(output_dir, rel_output_path)

    # Calculate filename
    output_filename_template = Template(preprocess(config.output_filename_template))
    try:
        output_filename = output_filename_template.render({**basic_context, "images": []})
    except Exception:
        output_filename = f"{file_basename}.md"

    output_file_path = os.path.join(full_output_dir, output_filename)
    
    if os.path.exists(output_file_path):
        if dry_run:
            console.log(f"[dry-run] Would rebuild meta for {shorten_path(file_name)} -> {shorten_path(output_file_path)}", fg="green")
        else:
            console.log(f"Rebuilding meta for {shorten_path(file_name)}", fg="green")
            
            input_hash = compute_file_hash(file_name)
            output_hash = compute_file_hash(output_file_path)
            image_files = "[]" 
            
            # expected_path should be relative to job output root.
            expected_rel_path = os.path.join(rel_output_path, output_filename)

            metadata_manager.upsert_entry(
                input_note_filename=os.path.basename(file_name),
                output_markdown_filename=output_filename,
                expected_path=expected_rel_path,
                actual_file_path=output_file_path,
                input_file_hash=input_hash,
                output_file_hash=output_hash,
                is_locked=False,
                image_files=image_files
            )
    else:
        # Output main file doesn't exist
        if dry_run: 
             console.log(f"[dry-run] Output not found for {shorten_path(file_name)}: expected {shorten_path(output_file_path)}", fg="blue")


def rebuild_metadata_directory(
    directory: str,
    output: str,
    config: SuperMDConfig,
    dry_run: bool = False
) -> None:
    metadata_manager = MetadataManager(output)
    try:
        for root, _, files in os.walk(directory):
            file_list = tqdm(files, desc="Rebuilding Metadata", unit="file")
            for file in file_list:
                 filename = os.path.join(root, file)
                 if file.lower().endswith(SUPPORTED_EXTENSIONS):
                     rebuild_metadata_for_file(filename, config, output, metadata_manager, dry_run=dry_run)
    finally:
        metadata_manager.close()


def clean_metadata_directory(directory: str, dry_run: bool = False) -> None:
    meta_db = os.path.join(directory, ".meta", "metadata")
    if os.path.exists(meta_db):
        if dry_run:
            console.log(f"[dry-run] Would delete DB: {shorten_path(meta_db)}", fg="red")
        else:
            MetadataManager.remove_db(directory)
            console.log(f"Deleted DB: {shorten_path(meta_db)}", fg="red")
    else:
        console.info(f"No metadata DB found in {directory}")

    candidate_dirs = []
    
    for root, dirs, _ in os.walk(directory):
        if ".meta" in dirs:
            meta_path = os.path.join(root, ".meta")
            if os.path.abspath(directory) == os.path.abspath(root) and not dry_run: 
                 pass
            candidate_dirs.append(meta_path)

    if candidate_dirs:
        console.info(f"Found {len(candidate_dirs)} .meta directories to clean in {directory}")
        for meta_path in candidate_dirs:
            if dry_run:
                console.log(f"[dry-run] Would delete: {shorten_path(meta_path)}", fg="red")
            else:
                try:
                    shutil.rmtree(meta_path)
                    console.log(f"Deleted: {shorten_path(meta_path)}", fg="red")
                except Exception as e:
                    console.error(f"Failed to delete {meta_path}: {e}")
