import os
import click
from supermd.metadata_db import MetadataManager


def print_job_report(resolved: dict, verbose: bool) -> None:
    """Print metadata report for a resolved job dict (from config.resolve_job)."""
    out_path = resolved["output"]
    in_path = resolved["input"]

    manager = MetadataManager(out_path)
    entries = manager.get_all_entries()
    manager.close()

    print(click.style(f"\nJob: {resolved['name']}", fg="blue", bold=True))

    # 1. Analyze Tracked Entries
    tracked_basenames = set()
    if entries:
        print(click.style(f"  Tracked ({len(entries)}):", fg="cyan"))
        for entry in entries:
            tracked_basenames.add(entry.input_note_filename)

            status_parts = []
            if entry.is_locked:
                status_parts.append(click.style("Locked", fg="yellow"))
            else:
                status_parts.append(click.style("Active", fg="green"))

            if entry.actual_file_path and not os.path.exists(entry.actual_file_path):
                    status_parts.append(click.style("Broken", fg="red", bold=True))

            full_output_path = entry.actual_file_path if entry.actual_file_path else f"({entry.expected_path})"

            if verbose:
                print(f"    {click.style(entry.input_note_filename, bold=True)}")
                print(f"      Output: {full_output_path}")
                print(f"      Status: {' | '.join(status_parts)}")
                print(f"      Hashes: In={entry.input_file_hash[:8]}... Out={entry.output_file_hash[:8] if entry.output_file_hash else 'None'}...")
                print(f"      Images: {len(entry.image_files) if entry.image_files else 0} chars (JSON)")
            else:
                print(f"    {entry.input_note_filename} -> {full_output_path} [{' | '.join(status_parts)}]")
    else:
            print(click.style("  Tracked: None", dim=True))

    # 2. Analyze Untracked Files
    untracked = []
    if os.path.exists(in_path):
        supported_exts = ('.note', '.pdf', '.png', '.spd')
        for root, _, files in os.walk(in_path):
            for file in files:
                if file.lower().endswith(supported_exts):
                    if file not in tracked_basenames:
                        rel_path = os.path.relpath(os.path.join(root, file), in_path)
                        untracked.append(rel_path)

    if untracked:
        print(click.style(f"  Untracked ({len(untracked)}):", fg="magenta"))
        for f in untracked:
                print(f"    {f} [Pending/New]")
    else:
        if os.path.exists(in_path):
            print(click.style("  Untracked: None (All matched)", fg="green"))
        else:
            print(click.style(f"  Input directory not found: {in_path}", fg="red"))
