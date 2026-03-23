"""Tests for core.hooks.tool_name_sanitizer — ToolNameSanitizer."""

from __future__ import annotations

from unittest.mock import MagicMock

from strands_compose.hooks.tool_name_sanitizer import (
    ToolNameSanitizer,
    _sanitize,
)


class TestSanitize:
    def test_exact_match(self):
        assert _sanitize("query", {"query", "list"}) == "query"

    def test_prefix_match_on_garbage(self):
        assert _sanitize("query<|extra|>", {"query", "list"}) == "query"

    def test_stripped_match(self):
        assert _sanitize("<query>", {"query", "list"}) == "query"

    def test_no_match_returns_none(self):
        assert _sanitize("unknown", {"query"}) is None

    def test_no_garbage_no_match_returns_none(self):
        assert _sanitize("unknown_tool", {"query"}) is None

    def test_segment_join_with_underscore(self):
        """e.g. reporter<|channel|>commentary -> reporter_channel_commentary."""
        assert (
            _sanitize("reporter<|channel|>commentary", {"reporter_channel_commentary"})
            == "reporter_channel_commentary"
        )

    def test_segment_join_with_hyphen(self):
        assert _sanitize("foo<|bar|>baz", {"foo-bar-baz"}) == "foo-bar-baz"

    def test_segment_join_concatenated(self):
        assert _sanitize("foo<|bar|>baz", {"foobarbaz"}) == "foobarbaz"


class TestToolNameSanitizer:
    def _make_agent(self, tool_names):
        agent = MagicMock()
        agent.tool_registry.registry = {n: MagicMock() for n in tool_names}
        return agent

    def test_register_hooks(self):
        sanitizer = ToolNameSanitizer()
        registry = MagicMock()
        sanitizer.register_hooks(registry)
        assert registry.add_callback.call_count == 2

    def test_known(self):
        agent = self._make_agent(["query", "list"])
        names = ToolNameSanitizer._known(agent)
        assert names == {"query", "list"}

    def test_on_after_model_fixes_garbled_name(self):
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.stop_response.message = {
            "content": [{"toolUse": {"name": "query<|channel|>", "input": {}}}]
        }
        sanitizer._on_after_model(event)
        assert event.stop_response.message["content"][0]["toolUse"]["name"] == "query"

    def test_on_after_model_skips_valid_name(self):
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.stop_response.message = {"content": [{"toolUse": {"name": "query", "input": {}}}]}
        sanitizer._on_after_model(event)
        assert event.stop_response.message["content"][0]["toolUse"]["name"] == "query"

    def test_on_after_model_leaves_unresolvable_garbled_name(self):
        """Garbled name that can't be mapped is left intact for BeforeToolCall to cancel."""
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.stop_response.message = {"content": [{"toolUse": {"name": "<|bad|>", "input": {}}}]}
        sanitizer._on_after_model(event)
        # Name should be unchanged — not stripped to "bad"
        assert event.stop_response.message["content"][0]["toolUse"]["name"] == "<|bad|>"

    def test_on_after_model_no_stop_response(self):
        sanitizer = ToolNameSanitizer()
        event = MagicMock()
        event.stop_response = None
        sanitizer._on_after_model(event)  # should not raise

    def test_on_before_tool_fixes_garbled(self):
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.tool_use = {"name": "query<|extra|>"}
        sanitizer._on_before_tool(event)
        assert event.tool_use["name"] == "query"

    def test_on_before_tool_cancels_if_no_match(self):
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.tool_use = {"name": "<|totally_unknown|>"}
        sanitizer._on_before_tool(event)
        assert event.cancel_tool  # should be set to error message

    def test_on_before_tool_skips_known_name(self):
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.tool_use = {"name": "query"}
        sanitizer._on_before_tool(event)
        assert event.tool_use["name"] == "query"

    def test_on_before_tool_skips_clean_unknown_name(self):
        """Clean unknown names are not this hook's job — Strands handles them."""
        sanitizer = ToolNameSanitizer()
        agent = self._make_agent(["query"])
        event = MagicMock()
        event.agent = agent
        event.tool_use = {"name": "nonexistent_tool"}
        event.cancel_tool = False
        sanitizer._on_before_tool(event)
        assert event.cancel_tool is False  # not touched
