from __future__ import annotations

# Re-export the main application and helpers from backend.main for backward compatibility
from backend.main import app, _read_reference_items

__all__ = ["app", "_read_reference_items"]
