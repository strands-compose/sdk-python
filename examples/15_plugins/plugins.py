"""Plugin factory for the 15_plugins example.

``ContextInjector`` takes a render callback rather than a plain value, so it
cannot be constructed from YAML params alone. A factory builds the callback and
returns the ready plugin; strands-compose calls the factory exactly as it would
call a plugin class, so the ``config.yaml`` entry looks identical either way.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from strands.vended_plugins.context_injector import ContextInjector


def _render_utc_clock(_context: Any) -> str:
    """Render the current UTC time as an injectable context block."""
    now = datetime.now(timezone.utc).isoformat()
    return f"<current_utc_time>{now}</current_utc_time>"


def make_clock_injector() -> ContextInjector:
    """Build a ContextInjector that folds the current UTC time into each model call."""
    return ContextInjector(_render_utc_clock, name="clock")
