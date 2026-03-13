import os
import time
import shutil
import pytest
from supermd.metadata_db import MetadataManager, InputNotChangedError, OutputChangedError
from supermd.converter import verify_metadata_file
from supermd.utils import compute_file_hash

@pytest.fixture
def test_dirs(tmp_path):
    input_file = tmp_path / "test.note"
    output_dir = tmp_path / "output"
    output_file = output_dir / "test.md"
    metadata_dir = output_dir / ".meta"
    
    output_dir.mkdir()
    metadata_dir.mkdir()
    
    return {
        "input": str(input_file),
        "output": str(output_file), 
        "meta": str(metadata_dir)
    }

def test_metadata_feedback(test_dirs):
    input_file = test_dirs["input"]
    output_file = test_dirs["output"]
    metadata_dir = test_dirs["meta"]
    
    # We need the parent of .meta for MetadataManager, which is output_dir
    output_dir_path = os.path.dirname(metadata_dir)
    manager = MetadataManager(output_dir_path)

    try:
        # 1. Initial Setup
        with open(input_file, "wb") as f:
            f.write(b"original content")
        with open(output_file, "w") as f:
            f.write("# Original Markdown")
        
        input_hash = compute_file_hash(input_file)
        output_hash = compute_file_hash(output_file)
        
        manager.upsert_entry(
            input_note_filename=os.path.basename(input_file),
            output_markdown_filename=os.path.basename(output_file),
            expected_path=os.path.basename(output_file),
            actual_file_path=output_file,
            input_file_hash=input_hash,
            output_file_hash=output_hash,
            is_locked=False,
            image_files="[]"
        )

        # 2. Verify InputNotChangedError
        with pytest.raises(InputNotChangedError):
            verify_metadata_file(manager, input_file, input_hash)

        # 3. Verify Success on Input Change
        time.sleep(0.01)
        with open(input_file, "wb") as f:
            f.write(b"modified content")
        
        new_input_hash = compute_file_hash(input_file)
        
        # Should not raise exception
        verify_metadata_file(manager, input_file, new_input_hash)

        # Reset metadata for next step (simulate successful conversion)
        with open(output_file, "w") as f:
            f.write("# Modified Markdown")
        
        new_output_hash = compute_file_hash(output_file)
        manager.upsert_entry(
            input_note_filename=os.path.basename(input_file),
            output_markdown_filename=os.path.basename(output_file),
            expected_path=os.path.basename(output_file),
            actual_file_path=output_file,
            input_file_hash=new_input_hash,
            output_file_hash=new_output_hash,
            is_locked=False,
            image_files="[]"
        )

        # 4. Verify OutputChangedError
        # Change input again so it SHOULD process
        with open(input_file, "wb") as f:
            f.write(b"changed again")
        
        current_input_hash = compute_file_hash(input_file)
        
        # But modify output locally
        with open(output_file, "w") as f:
            f.write("# User Modified Markdown")

        with pytest.raises(OutputChangedError):
            verify_metadata_file(manager, input_file, current_input_hash)

        # 5. Verify ignoresnlock Property
        # Add ignoresnlock: true to the output file
        with open(output_file, "w") as f:
            f.write("---\nignoresnlock: true\n---\n# User Modified Markdown")
        
        # Should not raise exception
        verify_metadata_file(manager, input_file, current_input_hash)
    finally:
        manager.close()
