import time
from unittest.mock import MagicMock
from sn2md.watcher import DebouncedEventHandler

def test_debounced_event_handler():
    """Verify handler updates state on events."""
    handler = DebouncedEventHandler()
    
    event = MagicMock()
    event.is_directory = False
    event.src_path = "test.note"
    event.event_type = "modified"
    
    # Initial state
    assert handler.has_pending_changes is False
    assert handler.last_change_time == 0
    
    # Event triggers update
    handler.on_any_event(event)
    assert handler.has_pending_changes is True
    t1 = handler.last_change_time
    assert t1 > 0
    
    # Subsequent event updates time
    time.sleep(0.01)
    handler.on_any_event(event)
    t2 = handler.last_change_time
    assert t2 > t1
    assert handler.has_pending_changes is True
