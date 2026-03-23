"""Tests for ResolvedConfig.wire_event_queue() method."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from strands_compose.config.resolvers.config import ResolvedConfig
from strands_compose.wire import EventQueue


class TestWireEventQueue:
    """Unit tests for ResolvedConfig.wire_event_queue()."""

    @patch("strands_compose.config.resolvers.config.make_event_queue")
    def test_returns_event_queue(self, mock_make_eq):
        mock_eq = MagicMock(spec=EventQueue)
        mock_make_eq.return_value = mock_eq

        agent = MagicMock()
        agent.agent_id = "a"
        agent.hooks = MagicMock()
        agent.hooks._registered_callbacks = {}
        rc = ResolvedConfig(entry=agent, agents={"a": agent})

        result = rc.wire_event_queue()

        assert result is mock_eq
        mock_make_eq.assert_called_once()

    @patch("strands_compose.config.resolvers.config.make_event_queue")
    def test_passes_agents_and_orchestrators(self, mock_make_eq):
        mock_make_eq.return_value = MagicMock(spec=EventQueue)

        agent = MagicMock()
        agent.agent_id = "a"
        agent.hooks = MagicMock()
        agent.hooks._registered_callbacks = {}
        orch = MagicMock()

        rc = ResolvedConfig(
            entry=agent,
            agents={"a": agent},
            orchestrators={"o": orch},
        )
        rc.wire_event_queue()

        call_args = mock_make_eq.call_args
        assert call_args[0][0] == {"a": agent}
        assert call_args[1]["orchestrators"] == {"o": orch}

    @patch("strands_compose.config.resolvers.config.make_event_queue")
    def test_forwards_tool_labels(self, mock_make_eq):
        mock_make_eq.return_value = MagicMock(spec=EventQueue)

        agent = MagicMock()
        agent.agent_id = "a"
        agent.hooks = MagicMock()
        agent.hooks._registered_callbacks = {}

        rc = ResolvedConfig(entry=agent, agents={"a": agent})
        labels = {"a": "Custom Label"}
        rc.wire_event_queue(tool_labels=labels)

        assert mock_make_eq.call_args[1]["tool_labels"] == labels

    @patch("strands_compose.config.resolvers.config.make_event_queue")
    def test_none_tool_labels_by_default(self, mock_make_eq):
        mock_make_eq.return_value = MagicMock(spec=EventQueue)

        agent = MagicMock()
        agent.agent_id = "a"
        agent.hooks = MagicMock()
        agent.hooks._registered_callbacks = {}

        rc = ResolvedConfig(entry=agent, agents={"a": agent})
        rc.wire_event_queue()

        assert mock_make_eq.call_args[1]["tool_labels"] is None
