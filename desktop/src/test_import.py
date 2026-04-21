#!/usr/bin/env python3
"""Debug script to test imports."""

import sys
from pathlib import Path

def _src_root() -> Path:
    """Get the absolute path to the src directory."""
    return Path(__file__).resolve().parent

def _ensure_src_on_path() -> None:
    """Add the src directory to Python's module search path."""
    src_root = _src_root()
    src_value = str(src_root)
    if src_value not in sys.path:
        sys.path.insert(0, src_value)
    print(f"DEBUG: __file__ = {__file__}", file=sys.stderr)
    print(f"DEBUG: _src_root() = {src_root}", file=sys.stderr)
    print(f"DEBUG: sys.path[0] = {sys.path[0]}", file=sys.stderr)

_ensure_src_on_path()

try:
    from core.scheduler.event_scheduler import EventScheduler
    print("SUCCESS: EventScheduler imported", file=sys.stderr)
except ImportError as e:
    print(f"FAILED: {e}", file=sys.stderr)
