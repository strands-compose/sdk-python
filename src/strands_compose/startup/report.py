"""Startup health-check result types.

Provides :class:`CheckResult` for individual check outcomes,
:class:`StartupReport` for aggregated results, and
:class:`StartupError` raised when critical checks fail.
"""

from __future__ import annotations

import dataclasses
import logging
from typing import Literal

logger = logging.getLogger(__name__)

Severity = Literal["critical", "warning", "info"]


@dataclasses.dataclass
class CheckResult:
    """Result of a single startup validation check.

    Attributes:
        ok: ``True`` if the check passed.
        category: Validation category — ``"network"``, ``"config"``, or ``"runtime"``.
        subject: Identifier for what was checked (e.g. ``"model:bedrock"``, ``"mcp:postgres"``).
        message: One-line human-readable description of what was found.
        severity: Impact level — ``"critical"`` blocks startup,
            ``"warning"`` allows startup with degraded functionality,
            ``"info"`` is informational.
        hint: Actionable fix suggestion when the check fails.
        exception: Original exception that caused a failure.
    """

    ok: bool
    category: str
    subject: str
    message: str
    severity: Severity = "info"
    hint: str = ""
    exception: Exception | None = dataclasses.field(default=None, repr=False)

    def __str__(self) -> str:
        """Format the check result as a human-readable string."""
        icon = "\u2713" if self.ok else ("\u26a0" if self.severity == "warning" else "\u2717")
        parts = [f"[{self.category:8s}] {icon} {self.subject}: {self.message}"]
        if not self.ok and self.hint:
            parts.append(f"              hint: {self.hint}")
        return "\n".join(parts)

    @classmethod
    def passed(cls, category: str, subject: str, message: str) -> CheckResult:
        """Create a passing ``info`` result."""
        return cls(ok=True, category=category, subject=subject, message=message)

    @classmethod
    def warn(
        cls,
        category: str,
        subject: str,
        message: str,
        *,
        hint: str = "",
        exception: Exception | None = None,
    ) -> CheckResult:
        """Create a non-critical ``warning`` result."""
        return cls(
            ok=False,
            category=category,
            subject=subject,
            message=message,
            severity="warning",
            hint=hint,
            exception=exception,
        )

    @classmethod
    def critical(
        cls,
        category: str,
        subject: str,
        message: str,
        *,
        hint: str = "",
        exception: Exception | None = None,
    ) -> CheckResult:
        """Create a ``critical`` failure result."""
        return cls(
            ok=False,
            category=category,
            subject=subject,
            message=message,
            severity="critical",
            hint=hint,
            exception=exception,
        )


class StartupError(Exception):
    """Raised when critical startup checks fail."""

    def __init__(self, report: StartupReport) -> None:
        """Initialize StartupError with the failing report.

        Args:
            report: The startup report containing critical failures.
        """
        self.report = report
        messages = [f"  - {c.subject}: {c.message}" for c in report.critical_checks]
        super().__init__("Startup failed:\n" + "\n".join(messages))


@dataclasses.dataclass
class StartupReport:
    """Aggregated startup validation results."""

    checks: list[CheckResult] = dataclasses.field(default_factory=list)

    @property
    def ok(self) -> bool:
        """``True`` if no critical checks failed."""
        return not any(c.severity == "critical" for c in self.checks)

    @property
    def warnings(self) -> list[CheckResult]:
        """Checks with ``severity="warning"``."""
        return [c for c in self.checks if c.severity == "warning"]

    @property
    def critical_checks(self) -> list[CheckResult]:
        """Checks with ``severity="critical"``."""
        return [c for c in self.checks if c.severity == "critical"]

    @property
    def passed_checks(self) -> list[CheckResult]:
        """Checks that passed (``ok=True``)."""
        return [c for c in self.checks if c.ok]

    def raise_if_critical(self) -> None:
        """Raise :exc:`StartupError` if any critical checks failed.

        Raises:
            StartupError: With a summary of all critical failures.
        """
        if not self.ok:
            raise StartupError(self)

    def print_summary(self, *, verbose: bool = False) -> None:
        """Print a human-readable summary to the log.

        Args:
            verbose: If ``True``, also print passing checks.
        """
        for check in self.checks:
            if verbose or not check.ok:
                logger.info("%s", check)

        n_ok = len(self.passed_checks)
        n_warn = len(self.warnings)
        n_crit = len(self.critical_checks)
        total = len(self.checks)
        status = "OK" if self.ok else "FAILED"
        suffix = ""
        if n_warn:
            suffix += f", {n_warn} warning(s)"
        if n_crit:
            suffix += f", {n_crit} critical"
        logger.info(
            "status=<%s>, passed=<%d>, total=<%d> | startup check summary%s",
            status,
            n_ok,
            total,
            suffix,
        )
