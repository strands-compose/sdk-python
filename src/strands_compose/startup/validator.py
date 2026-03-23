"""Startup validation checks for MCP servers, clients, and model endpoints.

Runs health probes AFTER config resolution to catch connectivity issues
before the user starts chatting.

**This module is opt-in** — ``validate_mcp()`` is NOT called automatically by
``load()`` or the serve pipeline.  Call it explicitly after
``mcp_lifecycle.start()`` when MCP clients are connected::

    infra = resolve_infra(app_config)
    infra.mcp_lifecycle.start()
    report = await validate_mcp(infra)  # no agent build needed
    report.print_summary()
"""

from __future__ import annotations

import asyncio
import logging
import urllib.error
import urllib.request
from typing import TYPE_CHECKING

from .report import CheckResult, StartupReport

if TYPE_CHECKING:
    from strands.tools.mcp import MCPClient as StrandsMCPClient

    from ..config.resolvers import ResolvedConfig, ResolvedInfra
    from ..mcp.server import MCPServer

logger = logging.getLogger(__name__)


async def validate_mcp(target: ResolvedConfig | ResolvedInfra) -> StartupReport:
    """Run all startup validation checks.

    Checks:
    1. MCP servers are reachable (HTTP probe).
    2. MCP clients have active sessions.

    Accepts either a :class:`ResolvedConfig` or :class:`ResolvedInfra` —
    only the ``mcp_lifecycle`` attribute is used, so agents are **not**
    required.  This avoids an unnecessary cold-start agent build when
    validating during ASGI lifespan startup.

    Args:
        target: A resolved config or infrastructure object with
            ``mcp_lifecycle``.

    Returns:
        StartupReport with all check results.
    """
    checks: list[CheckResult] = []

    server_tasks = [
        _check_mcp_server(name, server) for name, server in target.mcp_lifecycle.servers.items()
    ]
    client_tasks = [
        _check_mcp_client(name, client) for name, client in target.mcp_lifecycle.clients.items()
    ]

    # Run server probes concurrently, then gather client checks (which are fast)
    server_results = await asyncio.gather(*server_tasks, return_exceptions=True)
    for result in server_results:
        if isinstance(result, BaseException):
            checks.append(
                CheckResult.critical(
                    "network",
                    "mcp-server",
                    f"Unexpected error: {result}",
                    exception=result if isinstance(result, Exception) else None,
                )
            )
        else:
            checks.extend(result)

    # The same for clients checks
    client_results = await asyncio.gather(*client_tasks, return_exceptions=True)
    for result in client_results:
        if isinstance(result, BaseException):
            checks.append(
                CheckResult.warn(
                    "runtime",
                    "mcp-client",
                    f"Unexpected error: {result}",
                    hint="Client checks failed, but servers may still be healthy",
                    exception=result if isinstance(result, Exception) else None,
                )
            )
        else:
            checks.append(result)

    return StartupReport(checks=checks)


async def _check_mcp_server(name: str, server: MCPServer) -> list[CheckResult]:
    """Probe an MCP server's HTTP endpoint."""
    subject = f"mcp:{name}"
    return [await probe_http_health(subject, server.url)]


async def _check_mcp_client(name: str, client: StrandsMCPClient) -> CheckResult:
    """Check if an MCP client's session is active."""
    subject = f"mcp-client:{name}"
    try:
        tools = await client.load_tools()
        if tools is not None:
            return CheckResult.passed("runtime", subject, "Client has tool registry")
        return CheckResult.passed("runtime", subject, "Client is available")
    except Exception as exc:
        return CheckResult.warn(
            "runtime",
            subject,
            f"Client check failed: {exc}",
            hint=f"Ensure the MCP server for client '{name}' is running",
            exception=exc,
        )


async def probe_http_health(subject: str, url: str) -> CheckResult:
    """Probe an HTTP endpoint for reachability.

    Any HTTP response (including 4xx — e.g. 406 from an MCP endpoint that
    only accepts POST) is treated as *reachable*.  Only 5xx responses and
    connection-level failures (timeout, refused) are reported as problems.

    Args:
        subject: Human-readable subject name.
        url: URL to probe.

    Returns:
        CheckResult with pass/fail.
    """
    try:
        resp = await asyncio.to_thread(
            urllib.request.urlopen,
            url,
            timeout=5,  # noqa: S310
        )
        status = resp.status
        if status < 500:
            return CheckResult.passed("network", subject, f"HTTP {status}")
        return CheckResult.warn(
            "network",
            subject,
            f"HTTP {status}",
            hint=f"Service at {url} returned a server error",
        )
    except urllib.error.HTTPError as exc:
        # HTTPError is raised for 4xx/5xx but the server *is* reachable.
        if exc.code < 500:
            return CheckResult.passed("network", subject, f"HTTP {exc.code}")
        return CheckResult.warn(
            "network",
            subject,
            f"HTTP {exc.code}",
            hint=f"Service at {url} returned a server error",
        )
    except Exception as exc:
        return CheckResult.critical(
            "network",
            subject,
            f"Connection failed: {exc}",
            hint=f"Ensure the service is running at {url}",
            exception=exc,
        )
