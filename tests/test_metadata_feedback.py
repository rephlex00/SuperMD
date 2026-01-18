import os
import time
import shutil
import pytest
from sn2md.metadata import check_metadata_file, write_metadata_file, InputNotChangedError, OutputChangedError

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

    # 1. Initial Setup
    with open(input_file, "wb") as f:
        f.write(b"original content")
    with open(output_file, "w") as f:
        f.write("# Original Markdown")
    
    write_metadata_file(metadata_dir, input_file, output_file)

    # 2. Verify InputNotChangedError
    with pytest.raises(InputNotChangedError):
        check_metadata_file(metadata_dir, input_file)

    # 3. Verify Success on Input Change
    time.sleep(0.01)
    with open(input_file, "wb") as f:
        f.write(b"modified content")
    
    # Should not raise exception
    check_metadata_file(metadata_dir, input_file)

    # Reset metadata for next step
    with open(output_file, "w") as f:
        f.write("# Modified Markdown")
    write_metadata_file(metadata_dir, input_file, output_file)

    # 4. Verify OutputChangedError
    # Change input again so it SHOULD process
    with open(input_file, "wb") as f:
        f.write(b"changed again")
    
    # But modify output locally
    with open(output_file, "w") as f:
        f.write("# User Modified Markdown")

    with pytest.raises(OutputChangedError):
        check_metadata_file(metadata_dir, input_file)

    # 5. Verify ignoresnlock Property
    # Add ignoresnlock: true to the output file
    with open(output_file, "w") as f:
        f.write("---\nignoresnlock: true\n---\n# User Modified Markdown")
    
    # Should not raise exception
    check_metadata_file(metadata_dir, input_file)
