"""Pre-flight startup validation and health checking.

Usage::

    from strands_compose.startup import validate_mcp, StartupReport

    report = await validate_mcp(infra)  # or validate_mcp(resolved_config)
    report.print_summary()
    report.raise_if_critical()
"""

from __future__ import annotations

from .report import CheckResult, Severity, StartupError, StartupReport
from .validator import probe_http_health, validate_mcp

__all__ = [
    "CheckResult",
    "Severity",
    "StartupError",
    "StartupReport",
    "probe_http_health",
    "validate_mcp",
]
