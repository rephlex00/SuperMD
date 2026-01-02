
import time
from unittest.mock import MagicMock
from sn2md.watcher import DebouncedEventHandler

def test_debounced_event_handler():
    """Verify handler acts on debounce."""
    callback = MagicMock()
    handler = DebouncedEventHandler(callback, debounce_interval=0.1)
    
    event = MagicMock()
    event.is_directory = False
    event.src_path = "test"
    
    # First call
    handler.on_any_event(event)
    assert callback.call_count == 1
    
    # Immediate second call (should be ignored)
    handler.on_any_event(event)
    assert callback.call_count == 1
    
    # Wait and call again
    time.sleep(0.2)
    handler.on_any_event(event)
    assert callback.call_count == 2
