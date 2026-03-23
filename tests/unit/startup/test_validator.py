"""Tests for core.startup.validator — validate, probe_http_health, _check_mcp_client."""

from __future__ import annotations

import http.client
import urllib.error
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from strands_compose.startup.validator import (
    _check_mcp_client,
    probe_http_health,
    validate_mcp,
)


@pytest.mark.asyncio
class TestProbeHttpHealth:
    async def test_unreachable_returns_critical(self):
        result = await probe_http_health("test", "http://127.0.0.1:1")
        assert result.ok is False
        assert result.severity == "critical"

    @patch("urllib.request.urlopen")
    async def test_http_200_returns_passed(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_urlopen.return_value = mock_resp
        result = await probe_http_health("test", "http://localhost:8000")
        assert result.ok is True
        assert "HTTP 200" in result.message

    @patch("urllib.request.urlopen")
    async def test_http_404_returns_passed(self, mock_urlopen):
        """4xx responses mean the server is reachable — should pass."""
        exc = urllib.error.HTTPError(
            "http://localhost:8000",
            404,
            "Not Found",
            http.client.HTTPMessage(),
            BytesIO(b""),
        )
        mock_urlopen.side_effect = exc
        result = await probe_http_health("test", "http://localhost:8000")
        assert result.ok is True
        assert "HTTP 404" in result.message

    @patch("urllib.request.urlopen")
    async def test_http_406_returns_passed(self, mock_urlopen):
        """406 from MCP endpoint that only accepts POST — still reachable."""
        exc = urllib.error.HTTPError(
            "http://localhost:8000",
            406,
            "Not Acceptable",
            http.client.HTTPMessage(),
            BytesIO(b""),
        )
        mock_urlopen.side_effect = exc
        result = await probe_http_health("test", "http://localhost:8000")
        assert result.ok is True
        assert "HTTP 406" in result.message

    @patch("urllib.request.urlopen")
    async def test_http_500_returns_warning(self, mock_urlopen):
        exc = urllib.error.HTTPError(
            "http://localhost:8000",
            500,
            "Internal Server Error",
            http.client.HTTPMessage(),
            BytesIO(b""),
        )
        mock_urlopen.side_effect = exc
        result = await probe_http_health("test", "http://localhost:8000")
        assert result.ok is False
        assert result.severity == "warning"
        assert "HTTP 500" in result.message

    @patch("urllib.request.urlopen")
    async def test_http_503_returns_warning(self, mock_urlopen):
        exc = urllib.error.HTTPError(
            "http://localhost:8000",
            503,
            "Service Unavailable",
            http.client.HTTPMessage(),
            BytesIO(b""),
        )
        mock_urlopen.side_effect = exc
        result = await probe_http_health("test", "http://localhost:8000")
        assert result.ok is False
        assert result.severity == "warning"


@pytest.mark.asyncio
class TestCheckMcpClient:
    async def test_client_tools_loaded(self):
        client = AsyncMock()
        client.load_tools = AsyncMock(return_value=[MagicMock()])
        result = await _check_mcp_client("test", client)
        assert result.ok is True

    async def test_client_no_tools_still_passes(self):
        client = AsyncMock()
        client.load_tools = AsyncMock(return_value=None)
        result = await _check_mcp_client("test", client)
        assert result.ok is True

    async def test_client_raises_returns_warning(self):
        client = AsyncMock()
        client.load_tools = AsyncMock(side_effect=RuntimeError("fail"))
        result = await _check_mcp_client("test", client)
        assert result.severity == "warning"


@pytest.mark.asyncio
class TestValidate:
    async def test_empty_lifecycle(self):
        resolved = MagicMock()
        resolved.mcp_lifecycle.servers = {}
        resolved.mcp_lifecycle.clients = {}
        report = await validate_mcp(resolved)
        assert report.ok is True

    async def test_client_checks_included(self):
        resolved = MagicMock()
        resolved.mcp_lifecycle.servers = {}
        client = AsyncMock()
        client.load_tools = AsyncMock(return_value=[MagicMock()])
        resolved.mcp_lifecycle.clients = {"c1": client}
        report = await validate_mcp(resolved)
        assert report.ok is True
        assert len(report.checks) == 1
