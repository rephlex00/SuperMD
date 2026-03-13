import time
import os
from unittest.mock import MagicMock
from supermd.watcher import DebouncedEventHandler

def test_debounced_event_handler_basic():
    """Verify handler updates state on standard events."""
    handler = DebouncedEventHandler()
    
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/path/to/test.note"
    event.event_type = "modified"
    
    # Initial state
    assert handler.has_pending_changes is False
    assert handler.last_change_time == 0
    
    # Event triggers update
    handler.on_any_event(event)
    assert handler.has_pending_changes is True
    assert handler.last_change_time > 0

def test_ignore_hidden_files():
    """Verify handler ignores hidden files."""
    handler = DebouncedEventHandler()
    
    # Hidden file
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/path/to/.config"
    event.event_type = "modified"
    
    handler.on_any_event(event)
    assert handler.has_pending_changes is False

    # File in hidden directory
    event.src_path = "/path/to/.hidden/normal.txt"
    handler.on_any_event(event)
    assert handler.has_pending_changes is False

def test_atomic_save_moved_event():
    """Verify handler detects atomic saves (moved events)."""
    handler = DebouncedEventHandler()
    
    # Atomic save: .tmp -> file.txt
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/path/to/.tmp123"
    event.dest_path = "/path/to/file.txt"
    event.event_type = "moved"
    
    handler.on_any_event(event)
    assert handler.has_pending_changes is True

def test_ignore_moved_to_hidden():
    """Verify handler ignores moves into hidden files/dirs."""
    handler = DebouncedEventHandler()
    
    # Move to hidden
    event = MagicMock()
    event.is_directory = False
    event.src_path = "/path/to/file.txt"
    event.dest_path = "/path/to/.hidden_file"
    event.event_type = "moved"
    
    handler.on_any_event(event)
    assert handler.has_pending_changes is False
