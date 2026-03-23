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
    extract_last_text_block,
    extract_text_from_message,
    extract_text_from_node_result,
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


def _agent_result_with_text(text: str) -> AgentResult:
    """Build a minimal ``AgentResult`` whose message contains a single text block."""
    return AgentResult(
        stop_reason="end_turn",
        message=_msg([_text_block(text)]),
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
# extract_text_from_message
# ===========================================================================


class TestExtractTextFromMessage:
    """Unit tests for extract_text_from_message."""

    def test_returns_last_text_block(self) -> None:
        """Multiple text blocks in content returns the last one."""
        msg = _msg([_text_block("first"), _text_block("second")])
        assert extract_text_from_message(msg) == "second"

    def test_returns_none_for_no_text_blocks(self) -> None:
        """Content with only toolUse blocks returns None."""
        msg = _msg([_tool_use_block()])
        assert extract_text_from_message(msg) is None

    def test_returns_none_for_empty_content(self) -> None:
        """Empty content list returns None."""
        assert extract_text_from_message(_msg([])) is None

    def test_returns_none_for_none_message(self) -> None:
        """None message returns None."""
        assert extract_text_from_message(None) is None

    def test_skips_non_dict_blocks(self) -> None:
        """Non-dict items in content are safely skipped."""
        msg = cast(Message, {"role": "assistant", "content": ["raw string", _text_block("ok")]})
        assert extract_text_from_message(msg) == "ok"


# ===========================================================================
# extract_last_text_block — AgentResult path
# ===========================================================================


class TestExtractLastTextBlockAgentResult:
    """extract_last_text_block with AgentResult inputs."""

    def test_single_text_block(self) -> None:
        """Single text block is extracted."""
        result = _agent_result_with_text("hello")
        assert extract_last_text_block(result) == "hello"

    def test_multiple_text_blocks_returns_last(self) -> None:
        """Only the last text block is returned."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("a"), _text_block("b")]),
            metrics=MagicMock(),
            state={},
        )
        assert extract_last_text_block(result) == "b"

    def test_no_text_blocks_falls_back_to_str(self) -> None:
        """When no text blocks exist, falls back to str(AgentResult)."""
        result = _agent_result_no_text()
        text = extract_last_text_block(result)
        # str(AgentResult) produces empty string when only toolUse blocks exist
        assert isinstance(text, str)

    def test_interleaved_tool_use_and_text(self) -> None:
        """Text block after toolUse is correctly extracted."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("the answer")]),
            metrics=MagicMock(),
            state={},
        )
        assert extract_last_text_block(result) == "the answer"


# ===========================================================================
# extract_last_text_block — MultiAgentResult path (Swarm)
# ===========================================================================


class TestExtractLastTextBlockSwarmResult:
    """extract_last_text_block with SwarmResult inputs."""

    def test_extracts_from_last_swarm_node(self) -> None:
        """SwarmResult uses node_history to find the last agent's text."""
        reviewer_result = _agent_result_with_text("reviewed article")
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={
                "researcher": _node_result(_agent_result_with_text("raw research")),
                "reviewer": _node_result(reviewer_result),
            },
            node_history=_fake_swarm_nodes("researcher", "reviewer"),
        )
        assert extract_last_text_block(swarm_result) == "reviewed article"

    def test_extracts_from_single_agent_swarm(self) -> None:
        """SwarmResult with a single agent returns that agent's text."""
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"only_agent": _node_result(_agent_result_with_text("solo answer"))},
            node_history=_fake_swarm_nodes("only_agent"),
        )
        assert extract_last_text_block(swarm_result) == "solo answer"

    def test_empty_node_history_falls_back_to_reverse_scan(self) -> None:
        """Empty node_history falls back to scanning results in reverse."""
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"agent_a": _node_result(_agent_result_with_text("fallback text"))},
            node_history=[],
        )
        assert extract_last_text_block(swarm_result) == "fallback text"

    def test_empty_results_returns_descriptive_fallback(self) -> None:
        """SwarmResult with no node results returns a descriptive message."""
        swarm_result = SwarmResult(status=Status.COMPLETED, results={}, node_history=[])
        text = extract_last_text_block(swarm_result)
        assert "no text output" in text

    def test_last_node_not_in_results_falls_back_to_reverse_scan(self) -> None:
        """node_history references a node not in results — falls back gracefully."""
        swarm_result = SwarmResult(
            status=Status.COMPLETED,
            results={"agent_a": _node_result(_agent_result_with_text("found via fallback"))},
            node_history=_fake_swarm_nodes("missing_agent"),
        )
        assert extract_last_text_block(swarm_result) == "found via fallback"


# ===========================================================================
# extract_last_text_block — MultiAgentResult path (Graph)
# ===========================================================================


class TestExtractLastTextBlockGraphResult:
    """extract_last_text_block with GraphResult inputs."""

    def test_extracts_from_last_graph_node(self) -> None:
        """GraphResult uses execution_order to find the last node's text."""
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={
                "step_a": _node_result(_agent_result_with_text("intermediate")),
                "step_b": _node_result(_agent_result_with_text("final output")),
            },
            execution_order=_fake_graph_nodes("step_a", "step_b"),
        )
        assert extract_last_text_block(graph_result) == "final output"

    def test_empty_execution_order_falls_back(self) -> None:
        """Empty execution_order falls back to reverse scan of results."""
        graph_result = GraphResult(
            status=Status.COMPLETED,
            results={"node_x": _node_result(_agent_result_with_text("from reverse scan"))},
            execution_order=[],
        )
        assert extract_last_text_block(graph_result) == "from reverse scan"


# ===========================================================================
# extract_text_from_node_result — edge cases
# ===========================================================================


class TestExtractTextFromNodeResult:
    """Unit tests for extract_text_from_node_result."""

    def test_agent_result_with_text(self) -> None:
        """NodeResult wrapping an AgentResult extracts text."""
        nr = _node_result(_agent_result_with_text("answer"))
        assert extract_text_from_node_result(nr) == "answer"

    def test_nested_multi_agent_result(self) -> None:
        """NodeResult wrapping a nested MultiAgentResult recurses into it."""
        inner_multi = MultiAgentResult(
            status=Status.COMPLETED,
            results={"inner_agent": _node_result(_agent_result_with_text("nested answer"))},
        )
        nr = _node_result(inner_multi)
        assert extract_text_from_node_result(nr) == "nested answer"

    def test_exception_result_returns_error_message(self) -> None:
        """NodeResult wrapping an Exception returns a descriptive error string."""
        nr = _node_result(RuntimeError("something broke"))
        text = extract_text_from_node_result(nr)
        assert text is not None
        assert "something broke" in text

    def test_agent_result_without_text_falls_back_to_str(self) -> None:
        """AgentResult without text blocks falls back to str(AgentResult)."""
        ar = _agent_result_no_text()
        nr = _node_result(ar)
        text = extract_text_from_node_result(nr)
        # str(AgentResult) may be empty string for toolUse-only messages
        assert isinstance(text, str) or text is None


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
        assert tool("test") == "hello"


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
        assert tool("test query") == "agent response"

    def test_wraps_swarm_extracts_last_agent_text(self) -> None:
        """node_as_tool with a Swarm node extracts text from the last agent."""
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
        assert tool("write an article") == "polished article"

    def test_wraps_graph_extracts_last_node_text(self) -> None:
        """node_as_tool with a Graph node extracts text from the last executed node."""
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

        assert tool("run") == "final graph output"

    def test_custom_name_overrides_agent_id(self) -> None:
        """Explicit name= overrides the agent's own agent_id."""
        result = _agent_result_with_text("ok")
        tool = node_as_tool(
            self._agent(result, "original"), name="custom_name", description="Custom"
        )

        assert tool.tool_name == "custom_name"

    def test_multi_block_response_returns_last_text_block(self) -> None:
        """toolUse block followed by text block -> returns the text content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("answer")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == "answer"

    def test_multiple_text_blocks_returns_last(self) -> None:
        """Multiple text blocks -> only the last one is returned."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("part1"), _text_block("part2")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == "part2"

    def test_no_text_blocks_falls_back_to_str_result(self) -> None:
        """Only toolUse blocks -> str(result) fallback."""
        result = _agent_result_no_text()
        tool = node_as_tool(self._agent(result), description="desc")

        text = tool("q")
        assert isinstance(text, str)

    def test_single_text_block_returns_text(self) -> None:
        """Single text block -> returns its text directly."""
        result = _agent_result_with_text("only")
        tool = node_as_tool(self._agent(result), description="desc")

        assert tool("q") == "only"

    def test_empty_content_falls_back_to_str_result(self) -> None:
        """Empty content list -> str(result) fallback."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_tool(self._agent(result), description="desc")

        text = tool("q")
        assert isinstance(text, str)


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
    async def test_multi_block_response_returns_text_block(self) -> None:
        """toolUse block followed by text block -> returns the text content."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_tool_use_block(), _text_block("answer")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == "answer"

    @pytest.mark.asyncio
    async def test_multiple_text_blocks_returns_last(self) -> None:
        """Multiple text blocks -> only the last one is returned."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([_text_block("part1"), _text_block("part2")]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        assert await tool("q") == "part2"

    @pytest.mark.asyncio
    async def test_no_text_blocks_falls_back_to_str_result(self) -> None:
        """Only toolUse blocks -> str(result) fallback."""
        result = _agent_result_no_text()
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        text = await tool("q")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_empty_content_falls_back_to_str_result(self) -> None:
        """Empty content list -> str(result) fallback."""
        result = AgentResult(
            stop_reason="end_turn",
            message=_msg([]),
            metrics=MagicMock(),
            state={},
        )
        tool = node_as_async_tool(self._agent_with_async(result), description="desc")

        text = await tool("q")
        assert isinstance(text, str)

    @pytest.mark.asyncio
    async def test_async_wraps_swarm_extracts_last_agent_text(self) -> None:
        """node_as_async_tool with a Swarm node extracts the last agent's text."""
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

        assert await tool("q") == "final async answer"

    @pytest.mark.asyncio
    async def test_async_wraps_graph_extracts_last_node_text(self) -> None:
        """node_as_async_tool with a Graph node extracts the last node's text."""
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

        assert await tool("q") == "graph async final"
