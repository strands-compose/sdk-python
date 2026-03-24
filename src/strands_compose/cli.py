"""Command-line interface for strands-compose.

Exposes two sub-commands:

``check``
    Parse and validate a YAML config via :func:`load_config`.
    Pure, fast, zero side-effects — safe to run in CI and pre-deploy hooks.

``load``
    Full pipeline via :func:`load` followed by an async MCP health check
    via :func:`validate_mcp`.  Starts MCP server processes; always cleans
    them up before exiting.

Usage::

    strands-compose check config.yaml
    strands-compose check base.yaml agents.yaml   # multi-file merge
    strands-compose load  config.yaml [--json]
    strands-compose load  config.yaml [--quiet]

Exit codes: ``0`` on success, ``1`` on any error or critical health failure.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import textwrap
from importlib.metadata import version as pkg_version
from typing import TYPE_CHECKING

from .config import AppConfig, ConfigInput, load, load_config
from .startup.report import CheckResult, StartupReport
from .startup.validator import validate_mcp
from .utils import cli_errors

if TYPE_CHECKING:
    from .config.resolvers import ResolvedConfig

# ---------------------------------------------------------------------------
# ANSI helpers
# ---------------------------------------------------------------------------

_GREEN = "\033[32m"
_RED = "\033[31m"
_YELLOW = "\033[33m"
_DIM = "\033[2m"
_BOLD = "\033[1m"
_RESET = "\033[0m"


def _colour(text: str, code: str) -> str:
    """Wrap *text* in an ANSI colour code when stdout is a TTY.

    Args:
        text: The string to colour.
        code: An ANSI escape code string (e.g. ``_GREEN``).

    Returns:
        Coloured string if stdout is a TTY, plain string otherwise.
    """
    if sys.stdout.isatty():
        return f"{code}{text}{_RESET}"
    return text


def _get_version() -> str:
    """Return the installed package version.

    Returns:
        Version string from package metadata, or ``"unknown"`` as fallback.
    """
    try:
        return pkg_version("strands-compose")
    except Exception:
        return "unknown"


# ---------------------------------------------------------------------------
# check sub-command
# ---------------------------------------------------------------------------


def _count_hooks(app_config: AppConfig) -> int:
    """Count total hook entries across all agents and orchestrations.

    Args:
        app_config: The validated application config.

    Returns:
        Total number of hook entries.
    """
    total = 0
    for agent_def in app_config.agents.values():
        total += len(agent_def.hooks)
    for orch_def in app_config.orchestrations.values():
        total += len(orch_def.hooks)
    return total


def _render_check_success_ansi(app_config: AppConfig) -> None:
    """Print a human-readable success summary for the ``check`` sub-command.

    Args:
        app_config: The validated :class:`AppConfig` returned by
            :func:`load_config`.
    """
    agent_names = list(app_config.agents)
    orch_names = list(app_config.orchestrations)
    mcp_server_names = list(app_config.mcp_servers)
    mcp_client_names = list(app_config.mcp_clients)

    agent_str = f"{len(agent_names)} agent{'s' if len(agent_names) != 1 else ''}"
    if agent_names:
        agent_str += f" ({', '.join(agent_names)})"

    # Collect rows as (label, value) pairs, then align on the colon.
    rows: list[tuple[str, str]] = [
        ("entry", str(app_config.entry)),
        ("agents", agent_str),
    ]
    if app_config.models:
        rows.append(("models", ", ".join(app_config.models)))
    if mcp_server_names:
        rows.append(("mcp servers", ", ".join(mcp_server_names)))
    if mcp_client_names:
        rows.append(("mcp clients", ", ".join(mcp_client_names)))
    if orch_names:
        rows.append(("orchestrations", ", ".join(orch_names)))
    if app_config.session_manager:
        rows.append(("session", str(app_config.session_manager.type)))

    hook_count = _count_hooks(app_config)
    if hook_count:
        rows.append(("hooks", f"{hook_count} total"))

    width = max(len(label) for label, _ in rows)
    parts = [_colour("✓ Config valid", _GREEN + _BOLD)]
    for label, value in rows:
        parts.append(f"  {label.ljust(width)} : {value}")

    print("\n".join(parts))  # noqa: T201


def _render_check_success_json(app_config: AppConfig) -> None:
    """Print a JSON success payload for the ``check`` sub-command.

    Args:
        app_config: The validated :class:`AppConfig`.
    """
    payload = {
        "ok": True,
        "stage": "check",
        "version": _get_version(),
        "entry": app_config.entry,
        "agents": list(app_config.agents),
        "models": list(app_config.models),
        "mcp_clients": list(app_config.mcp_clients),
        "mcp_servers": list(app_config.mcp_servers),
        "orchestrations": list(app_config.orchestrations),
        "session_manager": app_config.session_manager.type if app_config.session_manager else None,
        "hooks": _count_hooks(app_config),
    }
    print(json.dumps(payload))  # noqa: T201


def _cmd_check(configs: list[ConfigInput], *, json_output: bool, quiet: bool) -> None:
    """Run the ``check`` sub-command.

    Calls :func:`load_config` and prints a success summary or exits with
    code 1 on any validation error (via :func:`cli_errors`).

    Args:
        configs: Paths to one or more YAML configuration files.
        json_output: When ``True``, emit JSON instead of ANSI output.
        quiet: When ``True``, suppress output on success (exit code only).
    """
    with cli_errors():
        config_input = configs[0] if len(configs) == 1 else configs
        app_config = load_config(config_input)

    if quiet:
        return

    if json_output:
        _render_check_success_json(app_config)
    else:
        _render_check_success_ansi(app_config)


# ---------------------------------------------------------------------------
# load sub-command
# ---------------------------------------------------------------------------


def _render_check_result_ansi(check: CheckResult) -> str:
    """Format one :class:`CheckResult` as a coloured ANSI line.

    Args:
        check: The check result to format.

    Returns:
        A single (possibly multi-line) string ready for printing.
    """
    if check.ok:
        icon = _colour("✓", _GREEN)
    elif check.severity == "warning":
        icon = _colour("⚠", _YELLOW)
    else:
        icon = _colour("✗", _RED)

    line = f"[{check.category:8s}] {icon} {check.subject}: {check.message}"
    if not check.ok and check.hint:
        indent = " " * 14
        line += f"\n{indent}{_colour('hint:', _DIM)} {check.hint}"
    return line


def _render_report_ansi(report: StartupReport) -> None:
    """Print a human-readable MCP health report to stdout.

    Args:
        report: The :class:`StartupReport` from :func:`validate_mcp`.
    """
    for check in report.checks:
        print(_render_check_result_ansi(check))  # noqa: T201

    n_ok = len(report.passed_checks)
    n_warn = len(report.warnings)
    n_crit = len(report.critical_checks)
    total = len(report.checks)

    if total == 0:
        print(_colour("✓ Load OK", _GREEN + _BOLD) + "  (no MCP servers/clients configured)")  # noqa: T201
        return

    summary = f"{n_ok}/{total} passed"
    if n_warn:
        summary += f", {n_warn} warning(s)"
    if n_crit:
        summary += f", {n_crit} critical"

    if report.ok:
        print(_colour(f"✓ Load OK  — {summary}", _GREEN + _BOLD))  # noqa: T201
    else:
        print(_colour(f"✗ Load FAILED — {summary}", _RED + _BOLD))  # noqa: T201


def _render_report_json(report: StartupReport) -> None:
    """Print a JSON health report to stdout.

    Args:
        report: The :class:`StartupReport` from :func:`validate_mcp`.
    """
    payload = {
        "ok": report.ok,
        "stage": "load",
        "version": _get_version(),
        "checks": [
            {
                "ok": c.ok,
                "category": c.category,
                "subject": c.subject,
                "message": c.message,
                "severity": c.severity,
                "hint": c.hint,
            }
            for c in report.checks
        ],
    }
    print(json.dumps(payload))  # noqa: T201


async def _cmd_load_async(configs: list[ConfigInput], *, json_output: bool, quiet: bool) -> None:
    """Async body of the ``load`` sub-command.

    Calls :func:`load`, runs :func:`validate_mcp`, prints the health
    report, and always stops the MCP lifecycle before returning.

    Args:
        configs: Paths to one or more YAML configuration files.
        json_output: When ``True``, emit JSON instead of ANSI output.
        quiet: When ``True``, suppress output on success (exit code only).

    Raises:
        SystemExit: With code 1 when any critical MCP health check fails.
    """
    resolved: ResolvedConfig | None = None
    try:
        with cli_errors():
            config_input = configs[0] if len(configs) == 1 else configs
            resolved = load(config_input)

        report = await validate_mcp(resolved)

        if not quiet or not report.ok:
            if json_output:
                _render_report_json(report)
            else:
                _render_report_ansi(report)

        if not report.ok:
            sys.exit(1)
    finally:
        if resolved is not None:
            resolved.mcp_lifecycle.stop()


def _cmd_load(configs: list[ConfigInput], *, json_output: bool, quiet: bool) -> None:
    """Run the ``load`` sub-command.

    Delegates to :func:`_cmd_load_async` via :func:`asyncio.run`.

    Args:
        configs: Paths to one or more YAML configuration files.
        json_output: When ``True``, emit JSON instead of ANSI output.
        quiet: When ``True``, suppress output on success (exit code only).
    """
    asyncio.run(_cmd_load_async(configs, json_output=json_output, quiet=quiet))


# ---------------------------------------------------------------------------
# Argument parser
# ---------------------------------------------------------------------------


def _add_common_flags(parser: argparse.ArgumentParser) -> None:
    """Add ``--json`` and ``--quiet`` flags shared by both sub-commands.

    Args:
        parser: The sub-command parser to extend.
    """
    parser.add_argument(
        "--json", dest="json_output", action="store_true", help="Emit JSON output instead of ANSI"
    )
    parser.add_argument(
        "-q",
        "--quiet",
        action="store_true",
        help="Suppress output on success (exit code only, useful for CI)",
    )


def _build_parser() -> argparse.ArgumentParser:
    """Build and return the top-level argument parser.

    Returns:
        Configured :class:`argparse.ArgumentParser`.
    """
    parser = argparse.ArgumentParser(
        prog="strands-compose",
        description=textwrap.dedent(
            """\
            strands-compose — YAML-driven multi-agent orchestration

            Sub-commands:
              check   Validate config (no side-effects, safe for CI)
              load    Full load + MCP health check
            """
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {_get_version()}",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<command>")
    subparsers.required = True

    # -- check --
    check_parser = subparsers.add_parser(
        "check",
        help="Parse and validate a YAML config (no side-effects)",
        description="Load and validate the config via load_config(). "
        "Checks YAML syntax, schema, variable interpolation, and "
        "cross-references. Exits 0 on success, 1 on any error.",
    )
    check_parser.add_argument(
        "config",
        metavar="CONFIG",
        nargs="+",
        help="Path(s) to YAML config file(s). Multiple files are merged left-to-right.",
    )
    _add_common_flags(check_parser)

    # -- load --
    load_parser = subparsers.add_parser(
        "load",
        help="Full load pipeline + MCP health check",
        description="Run the full load() pipeline (starts MCP servers, builds agents) "
        "then probe MCP connectivity. Always stops MCP servers on exit. "
        "Exits 0 on success, 1 on any error or critical health failure.",
    )
    load_parser.add_argument(
        "config",
        metavar="CONFIG",
        nargs="+",
        help="Path(s) to YAML config file(s). Multiple files are merged left-to-right.",
    )
    _add_common_flags(load_parser)

    return parser


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------


def main() -> None:
    """CLI entry point for the ``strands-compose`` command.

    Dispatches to :func:`_cmd_check` or :func:`_cmd_load` based on the
    sub-command supplied on the command line.
    """
    parser = _build_parser()
    args = parser.parse_args()

    if args.command == "check":
        _cmd_check(args.config, json_output=args.json_output, quiet=args.quiet)
    else:
        _cmd_load(args.config, json_output=args.json_output, quiet=args.quiet)
