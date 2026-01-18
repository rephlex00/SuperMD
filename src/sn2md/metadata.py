import hashlib
import logging
import os
import yaml
from dataclasses import asdict
from .types import ConversionMetadata
from .utils import shorten_path


logger = logging.getLogger(__name__)


def _metadata_filename(source_file: str) -> str:
    """Return a stable, per-source metadata filename."""
    base_name = os.path.splitext(os.path.basename(source_file))[0]
    safe_name = "".join(
        c if c.isalnum() or c in "-._" else "_"
        for c in base_name
    )
    digest = hashlib.sha1(os.path.abspath(source_file).encode("utf-8")).hexdigest()[:16]
    return f"{safe_name}-{digest}.yaml"


class InputNotChangedError(Exception):
    """Raised when the input file has not changed since the last conversion."""
    pass


class OutputChangedError(Exception):
    """Raised when the output file has been modified since the last conversion."""
    pass


def check_metadata_file(metadata_dir: str, source_file: str, dry_run: bool = False) -> ConversionMetadata | None:
    """Check the hashes of the source file against the metadata.

    Raises InputNotChangedError if the source file hasn't been modified.
    Raises OutputChangedError if the output file has been modified externally.

    Returns the computed source and output hashes.
    """
    if not os.path.isdir(metadata_dir):
        if dry_run:
             import click
             from tqdm import tqdm
             tqdm.write(click.style(f"  [dry-run] No metadata dir found at {shorten_path(metadata_dir)}", fg="blue"))
        return None

    metadata_path = os.path.join(metadata_dir, _metadata_filename(source_file))
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            data = yaml.safe_load(f)
            metadata = ConversionMetadata(**data)

            # Resolve paths (backward compatibility + relative support)
            output_file = metadata.output_file
            if not os.path.isabs(output_file):
                # Relative path: assume specific output file is in the parent of .meta dir
                # i.e. metadata_dir/../file.md
                output_file = os.path.normpath(os.path.join(metadata_dir, "..", output_file))

            input_file = metadata.input_file
            if not os.path.isabs(input_file):
                # Relative path: For input, we actually rely on the source_file passed in.
                # But we should verify the basename matches to ensure we are checking the right record.
                if os.path.basename(input_file) != os.path.basename(source_file):
                     # Metadata mismatch (different file name?)
                     return None
                input_file = source_file
            
            # Use resolved paths for checks
            real_metadata = ConversionMetadata(
                input_file=input_file,
                input_hash=metadata.input_hash,
                output_file=output_file,
                output_hash=metadata.output_hash
            )

            if not os.path.exists(real_metadata.output_file):
                # If output file is missing, we should re-generate it.
                if dry_run:
                     import click
                     from tqdm import tqdm
                     tqdm.write(click.style(f"  [dry-run] Output file missing: {shorten_path(real_metadata.output_file)}", fg="blue"))
                return None

            with open(real_metadata.output_file, "rb") as f:
                output_hash = hashlib.sha1(f.read()).hexdigest()

            if not os.path.exists(real_metadata.input_file):
                if dry_run:
                     import click
                     from tqdm import tqdm
                     tqdm.write(click.style(f"  [dry-run] Input file missing/moved: {shorten_path(real_metadata.input_file)}", fg="blue"))
                return None

            with open(real_metadata.input_file, "rb") as f:
                source_hash = hashlib.sha1(f.read()).hexdigest()

            if real_metadata.input_hash == source_hash:
                raise InputNotChangedError(f"Input {shorten_path(real_metadata.input_file)} has NOT changed!")
            else:
                msg = f"Input mismatch for {shorten_path(source_file)}: Stored={real_metadata.input_hash} Current={source_hash}"
                logger.info(msg)
                if dry_run:
                    import click
                    from tqdm import tqdm
                    tqdm.write(click.style(f"  [dry-run] {msg}", fg="yellow"))

            if real_metadata.output_hash != output_hash:
                # Check for ignoreSNLock property in the frontmatter
                with open(real_metadata.output_file, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
                    # Simple check for the property in the first few lines
                    import re
                    if re.search(r"^ignoresnlock:\s*true", content, re.MULTILINE | re.IGNORECASE):
                        # User explicitly opted out of safety lock
                        pass
                    else:
                        raise OutputChangedError(f"Output {shorten_path(real_metadata.output_file)} HAS been changed!")

            return real_metadata
    else:
        if dry_run:
             import click
             from tqdm import tqdm
             tqdm.write(click.style(f"  [dry-run] No metadata file found: {shorten_path(metadata_path)}", fg="blue"))
        return None


def write_metadata_file(metadata_dir: str, source_file: str, output_file: str) -> None:
    """Write the source hash and path to the metadata file."""
    os.makedirs(metadata_dir, exist_ok=True)
    with open(output_file, "rb") as f:
        output_hash = hashlib.sha1(f.read()).hexdigest()

    with open(source_file, "rb") as f:
        source_hash = hashlib.sha1(f.read()).hexdigest()

    metadata_path = os.path.join(metadata_dir, _metadata_filename(source_file))
    
    # Store only basenames for portability
    stored_input = os.path.basename(source_file)
    stored_output = os.path.basename(output_file)

    with open(metadata_path, "w") as f:
        yaml.dump(
            asdict(ConversionMetadata(
                input_file=stored_input,
                input_hash=source_hash,
                output_file=stored_output,
                output_hash=output_hash,
            )),
            f,
        )

