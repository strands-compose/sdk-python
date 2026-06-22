"""Tests for orchestrations.tools — node_as_tool and node_as_async_tool."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, cast
from unittest.mock import MagicMock

import pytest
from strands import Agent as _Agent
from strands.agent.agent_result import AgentResult
from strands.multiagent.base import MultiAgentBase, MultiAgentResult, NodeResult, Status
from strands.multiagent.graph import GraphResult
from strands.multiagent.swarm import SwarmResult
from strands.types.content import Message

from strands_compose.tools import (
    node_as_async_tool,
    node_as_tool,
)
from strands_compose.tools.extractors import (
    extract_last_message,
    extract_text,
    resolve_last_node_id,
)

# ---------------------------------------------------------------------------
# Helpers — lightweight stand-ins for SwarmNode / GraphNode dataclasses.
# Real SwarmNode/GraphNode require a full Agent executor; these fakes
# carry only ``node_id`` which is all ``resolve_last_node_id`` reads.
# ---------------------------------------------------------------------------


@dataclass
class _FakeSwarmNode:
    node_id: str


@dataclass
class _FakeGraphNode:
    node_id: str


def _msg(content: list[dict[str, Any]]) -> Message:
    """Build a ``Message`` dict with ``role`` and ``content``."""
    return cast(Message, {"role": "assistant", "content": content})


def _text_block(text: str) -> dict[str, str]:
    """Build a ``ContentBlock`` dict containing a text field."""
    return {"text": text}


def _tool_use_block() -> dict[str, Any]:
    """Build a ``ContentBlock`` dict containing a toolUse field."""
    return {"toolUse": {"toolUseId": "t1", "name": "calc", "input": {}}}


def _image_block() -> dict[str, Any]:
    """Build a ``ContentBlock`` dict containing image content."""
    return {"image": {"format": "png", "source": {"bytes": b"image-bytes"}}}


def _tool_result(content: list[dict[str, Any]]) -> dict[str, Any]:
    """Build the tool result dict returned by delegation wrappers."""
    return {"status": "success", "content": content}


def _agent_result_with_text(text: str) -> AgentResult:
    """Build a minimal ``AgentResult`` whose message contains a single text block."""
    return AgentResult(
        stop_reason="end_turn",
        message=_msg([_text_block(text)]),
        metrics=MagicMock(),
        state={},
    )


def _agent_result_with_content(content: list[dict[str, Any]]) -> AgentResult:
    """Build a minimal ``AgentResult`` whose message contains the given content."""
    return AgentResult(
        stop_reason="end_turn",
        message=_msg(content),
        metrics=MagicMock(),
        state={},
    )


def _agent_result_no_text() -> AgentResult:
    """Build an ``AgentResult`` with only toolUse blocks (no text)."""
    return AgentResult(
        stop_reason="end_turn",
        message=_msg([_tool_use_block()]),
        metrics=MagicMock(),
        state={},
    )


def _node_result(agent_result: AgentResult | MultiAgentResult | Exception) -> NodeResult:
    """Wrap an inner result in a ``NodeResult``."""
    return NodeResult(result=agent_result, status=Status.COMPLETED)


def _fake_swarm_nodes(*names: str) -> list[Any]:
    """Build a list of fake SwarmNode-like objects for ``node_history``."""
    return [_FakeSwarmNode(n) for n in names]


def _fake_graph_nodes(*names: str) -> list[Any]:
    """Build a list of fake GraphNode-like objects for ``execution_order``."""
    return [_FakeGraphNode(n) for n in names]


# ===========================================================================
# extract_text
# ===========================================================================


class TestExtractText:
    """Unit tests for extract_text."""

    def test_returns_last_text_block(self) -> None:
        """Multiple text blocks in content returns the last one."""
        msg = _msg([_text_block("first"), _text_block("second")])
        assert extract_text(msg) == "second"

    def test_returns_empty_string_for_no_text_blocks(self) -> None:
        """Content with only toolUse blocks returns an empty string."""
        msg = _msg([_tool_use_block()])
        assert extract_text(msg) == ""

    def test_returns_empty_string_for_empty_content(self) -> None:
        """Empty content list returns an empty string."""
        assert extract_text(_msg([])) == ""

    def test_returns_empty_string_for_none_message(self) -> None:
        """None message returns an empty string."""
        assert extract_text(None) == ""

    def test_skips_non_dict_blocks(self) -> None:
        """Non-dict items in content are safely skipped."""
        msg = cast(Message, {"role": "assistant", "content": ["raw string", _text_block("ok")]})
        assert extract_text(msg) == "ok"


# ===========================================================================
# extract_last_message - AgentResult path
# ===========================================================================


class TestExtractLastMessageAgentResult:
    """extract_last_message with AgentResult inputs."""

    def test_returns_agent_result_message(self) -> None:
        """AgentResult returns its complete message."""
        result = _agent_result_with_text("hello")
        assert extract_last_message(result) == result.message

    def test_preserves_multiple_text_blocks(self) -> None:
        """Multiple text blocks remain in the returned message."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("a"), _text_block("b")]),
            metrics=MagicMock(),
            state={},
        )
        assert extract_last_message(result)["content"] == [_text_block("a"), _text_block("b")]

    def test_preserves_non_text_blocks(self) -> None:
        """Image blocks remain in the returned message."""
        result = _agent_result_with_content([_image_block()])
        assert extract_last_message(result) == result.message

    def test_tool_use_only_message_is_returned(self) -> None:
        """Messages without text are still returned intact."""
        result = _agent_result_no_text()
        assert extract_last_message(result) == result.message

    def test_interleaved_tool_use_and_text(self) -> None:
        """Tool use and text blocks are both preserved."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("the answer")]),
            metrics=MagicMock(),
            state={},
        )
        assert extract_last_message(result)["content"] == [
            _tool_use_block(),
            _text_block("the answer"),
        ]


# ===========================================================================
# extract_last_message - MultiAgentResult path (Swarm)
# ===========================================================================


class TestExtractLastMessageSwarmResult:
    """extract_last_message with SwarmResult inputs."""

    def test_extracts_message_from_last_swarm_node(self) -> None:
        """SwarmResult uses node_history to find the last agent's message."""
        reviewer_result = _agent_result_with_text("reviewed article")
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "researcher": _node_result(_agent_result_with_text("raw research")),
                "reviewer": _node_result(reviewer_result),
            },
            node_history=_fake_swarm_nodes("researcher", "reviewer"),
        )
        assert extract_last_message(swarm_result) == reviewer_result.message

    def test_extracts_message_from_single_agent_swarm(self) -> None:
        """SwarmResult with a single agent returns that agent's message."""
        agent_result = _agent_result_with_text("solo answer")
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"only_agent": _node_result(agent_result)},
            node_history=_fake_swarm_nodes("only_agent"),
        )
        assert extract_last_message(swarm_result) == agent_result.message

    def test_preserves_non_text_blocks_from_swarm(self) -> None:
        """SwarmResult preserves non-text content from the last agent."""
        final_result = _agent_result_with_content([_image_block()])
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"image_agent": _node_result(final_result)},
            node_history=_fake_swarm_nodes("image_agent"),
        )
        assert extract_last_message(swarm_result) == final_result.message

    def test_empty_node_history_falls_back_to_reverse_scan(self) -> None:
        """Empty node_history falls back to scanning results in reverse."""
        agent_result = _agent_result_with_text("fallback text")
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"agent_a": _node_result(agent_result)},
            node_history=[],
        )
        assert extract_last_message(swarm_result) == agent_result.message

    def test_empty_results_returns_descriptive_fallback(self) -> None:
        """SwarmResult with no node results returns a descriptive text message."""
        swarm_result = SwarmResult(status=Status.COMPLETED, results={}, node_history=[])
        text = extract_text(extract_last_message(swarm_result))
        assert text is not None and "no message output" in text

    def test_last_node_not_in_results_falls_back_to_reverse_scan(self) -> None:
        """node_history references a node not in results — falls back gracefully."""
        agent_result = _agent_result_with_text("found via fallback")
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"agent_a": _node_result(agent_result)},
            node_history=_fake_swarm_nodes("missing_agent"),
        )
        assert extract_last_message(swarm_result) == agent_result.message


# ===========================================================================
# extract_last_message - MultiAgentResult path (Graph)
# ===========================================================================


class TestExtractLastMessageGraphResult:
    """extract_last_message with GraphResult inputs."""

    def test_extracts_message_from_last_graph_node(self) -> None:
        """GraphResult uses execution_order to find the last node's message."""
        final_result = _agent_result_with_text("final output")
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={
                "step_a": _node_result(_agent_result_with_text("intermediate")),
                "step_b": _node_result(final_result),
            },
            execution_order=_fake_graph_nodes("step_a", "step_b"),
        )
        assert extract_last_message(graph_result) == final_result.message

    def test_empty_execution_order_falls_back(self) -> None:
        """Empty execution_order falls back to reverse scan of results."""
        agent_result = _agent_result_with_text("from reverse scan")
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={"node_x": _node_result(agent_result)},
            execution_order=[],
        )
        assert extract_last_message(graph_result) == agent_result.message


# ===========================================================================
# extract_message_from_node_result - edge cases
# ===========================================================================


class TestExtractMessageFromNodeResult:
    """Unit tests for NodeResult handling in extract_last_message."""

    def test_agent_result_with_text(self) -> None:
        """NodeResult wrapping an AgentResult extracts the message."""
        agent_result = _agent_result_with_text("answer")
        node_result = _node_result(agent_result)
        assert extract_last_message(node_result) == agent_result.message

    def test_nested_multi_agent_result(self) -> None:
        """NodeResult wrapping a nested MultiAgentResult recurses into it."""
        agent_result = _agent_result_with_text("nested answer")
        inner_multi = MultiAgentResult(
            status=Status.COMPLETED,
            results={"inner_agent": _node_result(agent_result)},
        )
        node_result = _node_result(inner_multi)
        assert extract_last_message(node_result) == agent_result.message

    def test_exception_result_returns_error_message(self) -> None:
        """NodeResult wrapping an Exception returns a descriptive error string."""
        node_result = _node_result(RuntimeError("something broke"))
        message = extract_last_message(node_result)
        text = extract_text(message)
        assert text is not None
        assert "something broke" in text

    def test_agent_result_without_text_returns_message(self) -> None:
        """AgentResult without text blocks still returns its message."""
        agent_result = _agent_result_no_text()
        node_result = _node_result(agent_result)
        assert extract_last_message(node_result) == agent_result.message


# ===========================================================================
# resolve_last_node_id
# ===========================================================================


class TestResolveLastNodeId:
    """Unit tests for resolve_last_node_id."""

    def test_swarm_result_with_history(self) -> None:
        """Returns the last node_id from SwarmResult.node_history."""
        result = SwarmResult(
            status=Status.COMPLETED,
            node_history=_fake_swarm_nodes("a", "b"),
        )
        assert resolve_last_node_id(result) == "b"

    def test_graph_result_with_execution_order(self) -> None:
        """Returns the last node_id from GraphResult.execution_order."""
        result = GraphResult(
            status=Status.COMPLETED,
            execution_order=_fake_graph_nodes("x", "y"),
        )
        assert resolve_last_node_id(result) == "y"

    def test_base_multi_agent_result_returns_none(self) -> None:
        """Base MultiAgentResult has no history — returns None."""
        result = MultiAgentResult(status=Status.COMPLETED)
        assert resolve_last_node_id(result) is None

    def test_empty_history_returns_none(self) -> None:
        """Empty node_history returns None (falls through to execution_order check)."""
        result = SwarmResult(status=Status.COMPLETED, node_history=[])
        assert resolve_last_node_id(result) is None


# ===========================================================================
# node_as_tool with Agent — replaces former agent_as_tool
# ===========================================================================


class TestNodeAsToolWithAgent:
    """node_as_tool wraps an Agent with strict typing."""

    def _agent(self, result: AgentResult, agent_id: str = "agent1") -> MagicMock:
        agent = MagicMock(spec=_Agent)
        agent.return_value = result
        agent.agent_id = agent_id
        return agent

    def test_node_as_tool_wraps_agent(self) -> None:
        """node_as_tool wraps an Agent and produces a working tool."""
        result = _agent_result_with_text("hello")
        tool = node_as_tool(self._agent(result, "my_agent"), description="Use agent")

        assert tool.tool_name == "my_agent"
        assert tool("test") == _tool_result([_text_block("hello")])


# ===========================================================================
# node_as_tool — sync wrappers
# ===========================================================================


class TestNodeAsTool:
    """node_as_tool wraps Agent and MultiAgentBase nodes as @tool functions."""

    def _agent(self, result: AgentResult, agent_id: str = "agent1") -> MagicMock:
        agent = MagicMock(spec=_Agent)
        agent.return_value = result
        agent.agent_id = agent_id
        return agent

    def test_wraps_agent(self) -> None:
        """node_as_tool wraps an Agent; tool_name equals agent_id."""
        result = _agent_result_with_text("agent response")
        tool = node_as_tool(self._agent(result, "my_agent"), description="Use agent")

        assert tool.tool_name == "my_agent"
        assert tool("test query") == _tool_result([_text_block("agent response")])

    def test_wraps_swarm_extracts_last_agent_message_content(self) -> None:
        """node_as_tool with a Swarm node extracts content from the last agent."""
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "researcher": _node_result(_agent_result_with_text("raw data")),
                "reviewer": _node_result(_agent_result_with_text("polished article")),
            },
            node_history=_fake_swarm_nodes("researcher", "reviewer"),
        )
        multi = MagicMock(spec=MultiAgentBase)
        multi.return_value = swarm_result
        multi.id = "content_team"

        tool = node_as_tool(multi, name="content_team", description="Content production")

        assert tool.tool_name == "content_team"
        assert tool("write an article") == _tool_result([_text_block("polished article")])

    def test_wraps_graph_extracts_last_node_message_content(self) -> None:
        """node_as_tool with a Graph node extracts content from the last node."""
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={
                "step1": _node_result(_agent_result_with_text("intermediate")),
                "step2": _node_result(_agent_result_with_text("final graph output")),
            },
            execution_order=_fake_graph_nodes("step1", "step2"),
        )
        multi = MagicMock(spec=MultiAgentBase)
        multi.return_value = graph_result
        multi.id = "my_graph"

        tool = node_as_tool(multi, name="my_graph", description="Pipeline")

        assert tool("run") == _tool_result([_text_block("final graph output")])

    def test_custom_name_overrides_agent_id(self) -> None:
        """Explicit name= overrides the agent's own agent_id."""
        result = _agent_result_with_text("ok")
        tool = node_as_tool(
            self._agent(result, "original"), name="custom_name", description="Custom"
        )

        assert tool.tool_name == "custom_name"

    def test_multi_block_response_returns_tool_result_content(self) -> None:
        """toolUse block followed by text block returns supported content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("answer")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_text_block("answer")])

    def test_multiple_text_blocks_are_preserved(self) -> None:
        """Multiple text blocks are returned as message content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("part1"), _text_block("part2")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_text_block("part1"), _text_block("part2")])

    def test_image_blocks_are_preserved(self) -> None:
        """Image blocks are returned as tool result content."""
        result = _agent_result_with_content([_image_block()])
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_image_block()])

    def test_no_supported_blocks_returns_empty_text_content(self) -> None:
        """Only toolUse blocks return an empty text tool result."""
        result = _agent_result_no_text()
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_text_block("")])

    def test_single_text_block_returns_text(self) -> None:
        """Single text block returns a text tool result."""
        result = _agent_result_with_text("only")
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_text_block("only")])

    def test_empty_content_returns_empty_text_content(self) -> None:
        """Empty content list returns an empty text tool result."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == _tool_result([_text_block("")])


# ===========================================================================
# node_as_async_tool — async wrappers
# ===========================================================================


class TestNodeAsAsyncTool:
    """node_as_async_tool wraps agents for async delegation."""

    def _agent_with_async(self, result: AgentResult, agent_id: str = "agent1") -> MagicMock:
        agent = MagicMock(spec=_Agent)

        async def fake_invoke_async(query: str) -> AgentResult:
            return result

        agent.invoke_async = fake_invoke_async
        agent.agent_id = agent_id
        return agent

    @pytest.mark.asyncio
    async def test_multi_block_response_returns_tool_result_content(self) -> None:
        """toolUse block followed by text block returns supported content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("answer")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == _tool_result([_text_block("answer")])

    @pytest.mark.asyncio
    async def test_multiple_text_blocks_are_preserved(self) -> None:
        """Multiple text blocks are returned as message content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("part1"), _text_block("part2")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == _tool_result([_text_block("part1"), _text_block("part2")])

    @pytest.mark.asyncio
    async def test_image_blocks_are_preserved(self) -> None:
        """Image blocks are returned as tool result content."""
        result = _agent_result_with_content([_image_block()])
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == _tool_result([_image_block()])

    @pytest.mark.asyncio
    async def test_no_supported_blocks_returns_empty_text_content(self) -> None:
        """Only toolUse blocks return an empty text tool result."""
        result = _agent_result_no_text()
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == _tool_result([_text_block("")])

    @pytest.mark.asyncio
    async def test_empty_content_returns_empty_text_content(self) -> None:
        """Empty content list returns an empty text tool result."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == _tool_result([_text_block("")])

    @pytest.mark.asyncio
    async def test_async_wraps_swarm_extracts_last_agent_message_content(self) -> None:
        """node_as_async_tool with a Swarm node extracts last agent content."""
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "agent_a": _node_result(_agent_result_with_text("draft")),
                "agent_b": _node_result(_agent_result_with_text("final async answer")),
            },
            node_history=_fake_swarm_nodes("agent_a", "agent_b"),
        )
        multi = MagicMock(spec=MultiAgentBase)

        async def fake_invoke_async(query: str) -> SwarmResult:
            return swarm_result

        multi.invoke_async = fake_invoke_async
        multi.id = "swarm_orch"

        tool = node_as_async_tool(multi, name="swarm_orch", description="Swarm")

        assert await tool("q") == _tool_result([_text_block("final async answer")])

    @pytest.mark.asyncio
    async def test_async_wraps_graph_extracts_last_node_message_content(self) -> None:
        """node_as_async_tool with a Graph node extracts last node content."""
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={
                "s1": _node_result(_agent_result_with_text("step 1")),
                "s2": _node_result(_agent_result_with_text("graph async final")),
            },
            execution_order=_fake_graph_nodes("s1", "s2"),
        )
        multi = MagicMock(spec=MultiAgentBase)

        async def fake_invoke_async(query: str) -> GraphResult:
            return graph_result

        multi.invoke_async = fake_invoke_async
        multi.id = "graph_orch"

        tool = node_as_async_tool(multi, name="graph_orch", description="Graph")

        assert await tool("q") == _tool_result([_text_block("graph async final")])


# ===========================================================================
# serialize_multiagent_result
# ===========================================================================

from strands_compose.tools.extractors import serialize_multiagent_result  # noqa: E402


@dataclass
class _FakeGraphEdgeTuple:
    """Edge represented as a plain tuple (from_node, to_node)."""


@dataclass
class _FakeGraphEdgeObj:
    """Edge represented as a GraphEdge-like object with from_node / to_node attrs."""

    from_node: _FakeGraphNode
    to_node: _FakeGraphNode


class TestSerializeMultiagentResult:
    """Unit tests for serialize_multiagent_result."""

    # -- SwarmResult ---------------------------------------------------------

    def test_swarm_includes_last_node_id(self) -> None:
        """last_node_id is the final entry in node_history."""
        result = SwarmResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("a text"))},
            node_history=_fake_swarm_nodes("a"),
        )
        data = serialize_multiagent_result(result)
        assert data["last_node_id"] == "a"

    def test_swarm_includes_response_text(self) -> None:
        """response is the plain-text answer from the last node."""
        result = SwarmResult(
            status=Status.COMPLETED,
            results={"lead": _node_result(_agent_result_with_text("approved"))},
            node_history=_fake_swarm_nodes("lead"),
        )
        data = serialize_multiagent_result(result)
        assert data["response"] == "approved"

    def test_swarm_node_history_preserves_order_and_repeats(self) -> None:
        """swarm.node_history captures execution order including repeated visits."""
        result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "drafter": _node_result(_agent_result_with_text("draft")),
                "reviewer": _node_result(_agent_result_with_text("review")),
                "lead": _node_result(_agent_result_with_text("final")),
            },
            node_history=_fake_swarm_nodes("drafter", "lead", "reviewer", "lead", "lead"),
        )
        data = serialize_multiagent_result(result)
        assert data["swarm"]["node_history"] == ["drafter", "lead", "reviewer", "lead", "lead"]

    def test_swarm_last_node_id_from_history_not_dict_order(self) -> None:
        """last_node_id uses node_history, not results dict insertion order."""
        # results dict insertion order ends with "reviewer", but last in history is "lead"
        result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "drafter": _node_result(_agent_result_with_text("draft")),
                "lead": _node_result(_agent_result_with_text("APPROVED")),
                "reviewer": _node_result(_agent_result_with_text("looks good")),
            },
            node_history=_fake_swarm_nodes("drafter", "lead", "reviewer", "lead"),
        )
        data = serialize_multiagent_result(result)
        assert data["last_node_id"] == "lead"
        assert data["response"] == "APPROVED"

    def test_swarm_no_graph_section(self) -> None:
        """SwarmResult serialization does not produce a graph section."""
        result = SwarmResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("x"))},
            node_history=_fake_swarm_nodes("a"),
        )
        data = serialize_multiagent_result(result)
        assert "graph" not in data

    def test_swarm_includes_base_to_dict_fields(self) -> None:
        """Output includes all standard MultiAgentResult.to_dict() fields."""
        result = SwarmResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("x"))},
            node_history=_fake_swarm_nodes("a"),
        )
        data = serialize_multiagent_result(result)
        for key in ("type", "status", "results", "execution_count", "execution_time"):
            assert key in data

    # -- GraphResult ---------------------------------------------------------

    def test_graph_includes_last_node_id(self) -> None:
        """last_node_id is the final entry in execution_order."""
        result = GraphResult(
            status=Status.COMPLETED,
            results={"writer": _node_result(_agent_result_with_text("written"))},
            execution_order=_fake_graph_nodes("fetcher", "writer"),
        )
        data = serialize_multiagent_result(result)
        assert data["last_node_id"] == "writer"

    def test_graph_includes_response_text(self) -> None:
        """response is the plain-text answer from the last execution_order node."""
        result = GraphResult(
            status=Status.COMPLETED,
            results={"writer": _node_result(_agent_result_with_text("final output"))},
            execution_order=_fake_graph_nodes("fetcher", "writer"),
        )
        data = serialize_multiagent_result(result)
        assert data["response"] == "final output"

    def test_graph_execution_order_preserved(self) -> None:
        """graph.execution_order lists node ids in execution sequence."""
        result = GraphResult(
            status=Status.COMPLETED,
            results={"c": _node_result(_agent_result_with_text("c"))},
            execution_order=_fake_graph_nodes("a", "b", "c"),
        )
        data = serialize_multiagent_result(result)
        assert data["graph"]["execution_order"] == ["a", "b", "c"]

    def test_graph_edges_as_tuples(self) -> None:
        """graph.edges serializes tuple-based edges as [from, to] pairs."""
        n1, n2 = _FakeGraphNode("n1"), _FakeGraphNode("n2")
        result = GraphResult(
            status=Status.COMPLETED,
            results={"n2": _node_result(_agent_result_with_text("out"))},
            execution_order=cast(Any, [n1, n2]),
            edges=cast(Any, [(n1, n2)]),
        )
        data = serialize_multiagent_result(result)
        assert data["graph"]["edges"] == [["n1", "n2"]]

    def test_graph_edges_as_objects(self) -> None:
        """graph.edges serializes GraphEdge-like objects via from_node/to_node."""
        n1, n2 = _FakeGraphNode("src"), _FakeGraphNode("dst")
        edge = _FakeGraphEdgeObj(from_node=n1, to_node=n2)
        result = GraphResult(
            status=Status.COMPLETED,
            results={"dst": _node_result(_agent_result_with_text("done"))},
            execution_order=cast(Any, [n1, n2]),
            edges=cast(Any, [edge]),
        )
        data = serialize_multiagent_result(result)
        assert data["graph"]["edges"] == [["src", "dst"]]

    def test_graph_entry_points(self) -> None:
        """graph.entry_points lists entry node ids."""
        entry = _FakeGraphNode("start")
        result = GraphResult(
            status=Status.COMPLETED,
            results={"start": _node_result(_agent_result_with_text("go"))},
            execution_order=cast(Any, [entry]),
            entry_points=cast(Any, [entry]),
        )
        data = serialize_multiagent_result(result)
        assert data["graph"]["entry_points"] == ["start"]

    def test_graph_node_counts(self) -> None:
        """graph section includes completed, failed, and interrupted node counts."""
        result = GraphResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("x"))},
            execution_order=_fake_graph_nodes("a"),
            completed_nodes=3,
            failed_nodes=1,
            interrupted_nodes=0,
        )
        data = serialize_multiagent_result(result)
        assert data["graph"]["completed_nodes"] == 3
        assert data["graph"]["failed_nodes"] == 1
        assert data["graph"]["interrupted_nodes"] == 0

    def test_graph_no_swarm_section(self) -> None:
        """GraphResult serialization does not produce a swarm section."""
        result = GraphResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("x"))},
            execution_order=_fake_graph_nodes("a"),
        )
        data = serialize_multiagent_result(result)
        assert "swarm" not in data

    # -- Base MultiAgentResult -----------------------------------------------

    def test_base_result_no_swarm_or_graph_section(self) -> None:
        """Plain MultiAgentResult produces neither swarm nor graph section."""
        result = MultiAgentResult(
            status=Status.COMPLETED,
            results={"a": _node_result(_agent_result_with_text("plain"))},
        )
        data = serialize_multiagent_result(result)
        assert "swarm" not in data
        assert "graph" not in data
        assert data["last_node_id"] is None
        assert data["response"] == "plain"
