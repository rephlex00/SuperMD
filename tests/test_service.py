import os
from sn2md.service import generate_plist

def test_generate_plist(mock_workspace):
    """Verify plist content generation."""
    config_path = mock_workspace / "jobs.yaml"
    
    # We can't easily mock sys.executable in a subprocess-safe way for unit tests 
    # that import the module, but generate_plist uses logic to find the CLI.
    # We'll invoke it and check the structure.
    
    plist = generate_plist(str(config_path))
    
    assert "<?xml" in plist
    assert "<key>Label</key>" in plist
    assert "<string>com.sn2md.watch</string>" in plist
    
    # Check arguments
    assert "<string>watch</string>" in plist
    assert f"<string>{os.path.abspath(config_path)}</string>" in plist
    
    # Check environment variable injection
    assert "<key>PATH</key>" in plist
    assert "<key>PYTHONPATH</key>" in plist
