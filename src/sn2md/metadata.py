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


def check_metadata_file(metadata_dir: str, source_file: str) -> ConversionMetadata | None:
    """Check the hashes of the source file against the metadata.

    Raises a ValueError if the source file hasn't been modified.

    Returns the computed source and output hashes.
    """
    if not os.path.isdir(metadata_dir):
        return None

    metadata_path = os.path.join(metadata_dir, _metadata_filename(source_file))
    if os.path.exists(metadata_path):
        with open(metadata_path, "r") as f:
            data = yaml.safe_load(f)
            metadata = ConversionMetadata(**data)

            if not os.path.exists(metadata.output_file):
                raise ValueError("Output file does not exist anymore!")

            with open(metadata.output_file, "rb") as f:
                output_hash = hashlib.sha1(f.read()).hexdigest()

            if not os.path.exists(metadata.input_file):
                raise ValueError("Input file does not exist anymore!")

            with open(metadata.input_file, "rb") as f:
                source_hash = hashlib.sha1(f.read()).hexdigest()

            if metadata.input_hash == source_hash:
                raise ValueError(f"Input {shorten_path(metadata.input_file)} has NOT changed!")

            if metadata.output_hash != output_hash:
                raise ValueError(f"Output {shorten_path(metadata.output_file)} HAS been changed!")

            return metadata


def write_metadata_file(metadata_dir: str, source_file: str, output_file: str) -> None:
    """Write the source hash and path to the metadata file."""
    os.makedirs(metadata_dir, exist_ok=True)
    with open(output_file, "rb") as f:
        output_hash = hashlib.sha1(f.read()).hexdigest()

    with open(source_file, "rb") as f:
        source_hash = hashlib.sha1(f.read()).hexdigest()

    metadata_path = os.path.join(metadata_dir, _metadata_filename(source_file))
    with open(metadata_path, "w") as f:
        yaml.dump(
            asdict(ConversionMetadata(
                input_file=source_file,
                input_hash=source_hash,
                output_file=output_file,
                output_hash=output_hash,
            )),
            f,
        )

