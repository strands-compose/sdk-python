"""Delegation wrapping — node_as_tool / node_as_async_tool naming.

Result/message extraction (``extractors.py``) is covered in
``runtime/test_result_extraction.py``; this file stays focused on the wrapping.
"""

from __future__ import annotations

from strands import Agent

from strands_compose.tools import node_as_async_tool, node_as_tool
from tests.fakes import FakeModel


def _agent(agent_id: str) -> Agent:
    return Agent(model=FakeModel(), agent_id=agent_id)


def test_node_as_tool_defaults_name_to_agent_id():
    tool = node_as_tool(_agent("helper"), description="Delegate to helper")
    assert tool.tool_name == "helper"


def test_node_as_tool_accepts_explicit_name():
    tool = node_as_tool(_agent("helper"), name="ask_helper", description="d")
    assert tool.tool_name == "ask_helper"


def test_node_as_async_tool_defaults_name_to_agent_id():
    tool = node_as_async_tool(_agent("worker"), description="d")
    assert tool.tool_name == "worker"
