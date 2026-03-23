"""Tests for core.mcp.transports — transport factory functions."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from strands_compose.mcp.transports import (
    sse_transport,
    stdio_transport,
    streamable_http_transport,
)

# ===========================================================================
# stdio_transport
# ===========================================================================


class TestStdioTransport:
    """Tests for stdio_transport factory."""

    def test_empty_command_raises(self) -> None:
        """Empty command list is rejected with a clear error."""
        with pytest.raises(ValueError, match="non-empty"):
            stdio_transport([])

    def test_returns_callable(self) -> None:
        """Factory returns a callable."""
        t = stdio_transport(["python", "-m", "server"])
        assert callable(t)

    @patch("mcp.client.stdio.stdio_client")
    @patch("mcp.client.stdio.StdioServerParameters")
    def test_splits_command_into_command_and_args(
        self, mock_params_cls: MagicMock, mock_stdio_client: MagicMock
    ) -> None:
        """command[0] becomes 'command', command[1:] becomes 'args'."""
        factory = stdio_transport(["node", "--inspect", "server.js"])
        factory()

        mock_params_cls.assert_called_once_with(
            command="node",
            args=["--inspect", "server.js"],
            env=None,
            cwd=None,
            encoding="utf-8",
            encoding_error_handler="strict",
        )

    @patch("mcp.client.stdio.stdio_client")
    @patch("mcp.client.stdio.StdioServerParameters")
    def test_single_element_command_yields_empty_args(
        self, mock_params_cls: MagicMock, mock_stdio_client: MagicMock
    ) -> None:
        """A single-element command produces an empty args list."""
        factory = stdio_transport(["myserver"])
        factory()

        mock_params_cls.assert_called_once_with(
            command="myserver",
            args=[],
            env=None,
            cwd=None,
            encoding="utf-8",
            encoding_error_handler="strict",
        )

    @patch("mcp.client.stdio.stdio_client")
    @patch("mcp.client.stdio.StdioServerParameters")
    def test_passes_all_optional_params(
        self, mock_params_cls: MagicMock, mock_stdio_client: MagicMock
    ) -> None:
        """env, cwd, encoding, and encoding_error_handler are forwarded."""
        factory = stdio_transport(
            ["python", "srv.py"],
            env={"KEY": "val"},
            cwd="/tmp",
            encoding="ascii",
            encoding_error_handler="replace",
        )
        factory()

        mock_params_cls.assert_called_once_with(
            command="python",
            args=["srv.py"],
            env={"KEY": "val"},
            cwd="/tmp",
            encoding="ascii",
            encoding_error_handler="replace",
        )

    @patch("mcp.client.stdio.stdio_client")
    @patch("mcp.client.stdio.StdioServerParameters")
    def test_defensive_copy_of_command(
        self, mock_params_cls: MagicMock, mock_stdio_client: MagicMock
    ) -> None:
        """Mutating the original command list after creation has no effect."""
        cmd = ["python", "-m", "server"]
        factory = stdio_transport(cmd)
        cmd.append("--extra-flag")
        factory()

        _, kwargs = mock_params_cls.call_args
        assert kwargs["args"] == ["-m", "server"]  # no "--extra-flag"

    @patch("mcp.client.stdio.stdio_client")
    @patch("mcp.client.stdio.StdioServerParameters")
    def test_defensive_copy_of_env(
        self, mock_params_cls: MagicMock, mock_stdio_client: MagicMock
    ) -> None:
        """Mutating the original env dict after creation has no effect."""
        env = {"A": "1"}
        factory = stdio_transport(["python"], env=env)
        env["B"] = "2"
        factory()

        _, kwargs = mock_params_cls.call_args
        assert kwargs["env"] == {"A": "1"}  # no "B"


# ===========================================================================
# sse_transport
# ===========================================================================


class TestSseTransport:
    """Tests for sse_transport factory."""

    def test_empty_url_raises(self) -> None:
        """Empty URL is rejected."""
        with pytest.raises(ValueError, match="non-empty"):
            sse_transport("")

    def test_returns_callable(self) -> None:
        """Factory returns a callable."""
        t = sse_transport("http://localhost:8000/sse")
        assert callable(t)

    @patch("mcp.client.sse.sse_client")
    def test_passes_default_kwargs(self, mock_sse_client: MagicMock) -> None:
        """Default timeout/sse_read_timeout are forwarded; auth excluded."""
        factory = sse_transport("http://host/sse")
        factory()

        mock_sse_client.assert_called_once_with(
            url="http://host/sse",
            headers={},
            timeout=5,
            sse_read_timeout=300,
        )

    @patch("mcp.client.sse.sse_client")
    def test_auth_included_only_when_provided(self, mock_sse_client: MagicMock) -> None:
        """auth kwarg is only passed to sse_client when explicitly set."""
        auth_obj = MagicMock()
        factory = sse_transport("http://host/sse", auth=auth_obj)
        factory()

        kwargs = mock_sse_client.call_args[1]
        assert kwargs["auth"] is auth_obj

    @patch("mcp.client.sse.sse_client")
    def test_auth_excluded_when_none(self, mock_sse_client: MagicMock) -> None:
        """auth kwarg is absent from the call when not provided."""
        factory = sse_transport("http://host/sse")
        factory()

        kwargs = mock_sse_client.call_args[1]
        assert "auth" not in kwargs

    @patch("mcp.client.sse.sse_client")
    def test_httpx_client_factory_included_only_when_provided(
        self, mock_sse_client: MagicMock
    ) -> None:
        """httpx_client_factory kwarg is only passed when explicitly set."""
        client_factory = MagicMock()
        factory = sse_transport("http://host/sse", httpx_client_factory=client_factory)
        factory()

        kwargs = mock_sse_client.call_args[1]
        assert kwargs["httpx_client_factory"] is client_factory

    @patch("mcp.client.sse.sse_client")
    def test_httpx_client_factory_excluded_when_none(self, mock_sse_client: MagicMock) -> None:
        """httpx_client_factory kwarg is absent when not provided."""
        factory = sse_transport("http://host/sse")
        factory()

        kwargs = mock_sse_client.call_args[1]
        assert "httpx_client_factory" not in kwargs

    @patch("mcp.client.sse.sse_client")
    def test_custom_headers_and_timeouts(self, mock_sse_client: MagicMock) -> None:
        """Custom headers and timeouts are forwarded."""
        factory = sse_transport(
            "http://host/sse",
            headers={"Authorization": "Bearer tok"},
            timeout=10,
            sse_read_timeout=60,
        )
        factory()

        mock_sse_client.assert_called_once_with(
            url="http://host/sse",
            headers={"Authorization": "Bearer tok"},
            timeout=10,
            sse_read_timeout=60,
        )


# ===========================================================================
# streamable_http_transport
# ===========================================================================


class TestStreamableHttpTransport:
    """Tests for streamable_http_transport factory."""

    def test_empty_url_raises(self) -> None:
        """Empty URL is rejected."""
        with pytest.raises(ValueError, match="non-empty"):
            streamable_http_transport("")

    def test_returns_callable(self) -> None:
        """Factory returns a callable."""
        t = streamable_http_transport("http://localhost:8000/mcp")
        assert callable(t)

    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_bare_call_without_headers_or_client(self, mock_client: MagicMock) -> None:
        """No headers, no http_client → bare call with url and terminate_on_close."""
        factory = streamable_http_transport("http://host/mcp")
        factory()

        mock_client.assert_called_once_with(url="http://host/mcp", terminate_on_close=True)

    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_http_client_passed_directly(self, mock_client: MagicMock) -> None:
        """Pre-configured http_client is forwarded as-is."""
        custom_client = MagicMock()
        factory = streamable_http_transport("http://host/mcp", http_client=custom_client)
        factory()

        mock_client.assert_called_once_with(
            url="http://host/mcp",
            http_client=custom_client,
            terminate_on_close=True,
        )

    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_headers_ignored_when_http_client_provided(self, mock_client: MagicMock) -> None:
        """When http_client is given, headers param is silently ignored."""
        custom_client = MagicMock()
        factory = streamable_http_transport(
            "http://host/mcp",
            headers={"X-Custom": "val"},
            http_client=custom_client,
        )
        factory()

        # The call should use http_client, NOT create a new one from headers
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["http_client"] is custom_client

    @patch("httpx.AsyncClient")
    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_headers_create_httpx_client(
        self, mock_client: MagicMock, mock_async_client_cls: MagicMock
    ) -> None:
        """Headers without http_client → creates httpx.AsyncClient with those headers."""
        factory = streamable_http_transport(
            "http://host/mcp", headers={"Authorization": "Bearer tok"}
        )
        factory()

        mock_async_client_cls.assert_called_once_with(headers={"Authorization": "Bearer tok"})
        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["http_client"] is mock_async_client_cls.return_value

    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_terminate_on_close_false(self, mock_client: MagicMock) -> None:
        """terminate_on_close=False is forwarded."""
        factory = streamable_http_transport("http://host/mcp", terminate_on_close=False)
        factory()

        call_kwargs = mock_client.call_args[1]
        assert call_kwargs["terminate_on_close"] is False

    @patch("mcp.client.streamable_http.streamable_http_client")
    def test_defensive_copy_of_headers(self, mock_client: MagicMock) -> None:
        """Mutating the original headers dict after creation has no effect."""
        hdrs = {"X-Key": "original"}
        factory = streamable_http_transport("http://host/mcp", headers=hdrs)
        hdrs["X-Key"] = "mutated"
        hdrs["X-New"] = "injected"

        # We need to trigger the headers branch, so mock httpx too
        with patch("httpx.AsyncClient") as mock_httpx:
            factory()
            mock_httpx.assert_called_once_with(headers={"X-Key": "original"})
