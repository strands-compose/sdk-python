"""Message/result extraction (``extractors.py``) — the whole concern in one place.

Simple cases run on hand-built messages/``AgentResult``. The multi-agent cases
drive a real ``GraphResult`` / ``SwarmResult`` produced by invoking a real
orchestration through the public ``load_session`` seam (strands faked only at the
model resolver). Asserts the *shape* of the serialized dict and the extracted
message — the public contract of ``serialize_multiagent_result`` /
``extract_last_message`` / ``extract_text``.
"""

from __future__ import annotations

from strands.agent.agent_result import AgentResult
from strands.telemetry.metrics import EventLoopMetrics
from strands.types.content import Message

from strands_compose.config import load_session, resolve_infra
from strands_compose.config.schema import AppConfig
from strands_compose.tools import serialize_multiagent_result
from strands_compose.tools.extractors import extract_last_message, extract_text
from tests.factories import (
    agent_def,
    graph_orchestration,
    model_def,
    swarm_orchestration,
)

# ── extract_text / extract_last_message — simple cases ─────────────────────


def test_extract_text_returns_last_text_block():
    message: Message = {"role": "assistant", "content": [{"text": "final answer"}]}
    assert extract_text(message) == "final answer"


def test_extract_text_of_empty_message_is_empty_string():
    assert extract_text(None) == ""


def test_extract_last_message_returns_agent_result_message():
    message: Message = {"role": "assistant", "content": [{"text": "hi"}]}
    result = AgentResult(
        stop_reason="end_turn", message=message, metrics=EventLoopMetrics(), state={}
    )
    assert extract_last_message(result) == message


def test_extract_last_message_falls_back_for_unknown_result_type():
    assert extract_text(extract_last_message("just a string")) == "just a string"


# ── Multi-agent results — serialize + recursive extraction ─────────────────


async def _invoke(orch):
    """Build a two-agent orchestration and invoke it, returning the live result.

    Named models resolve through the ``config`` seam that ``fake_runtime`` patches,
    so invocation streams a FakeModel with no network.
    """
    config = AppConfig(
        models={"m": model_def()},
        agents={"a": agent_def(model="m"), "b": agent_def(model="m")},
        orchestrations={"o": orch},
        entry="o",
    )
    resolved = load_session(config, resolve_infra(config))
    return await resolved.entry.invoke_async("hi")


async def test_graph_result_serializes_execution_order_and_edges(fake_runtime):
    result = await _invoke(graph_orchestration("a", [("a", "b")]))

    data = serialize_multiagent_result(result)

    assert data["graph"]["execution_order"] == ["a", "b"]
    assert data["graph"]["edges"] == [["a", "b"]]
    assert data["last_node_id"] == "b"
    assert isinstance(data["response"], str) and data["response"]


async def test_swarm_result_serializes_node_history(fake_runtime):
    result = await _invoke(swarm_orchestration("a", ["a", "b"]))

    data = serialize_multiagent_result(result)

    history = data["swarm"]["node_history"]
    assert history  # at least the entry node executed
    assert data["last_node_id"] in history  # derived from history, not dict order


async def test_extract_last_message_unwraps_multiagent_result(fake_runtime):
    result = await _invoke(graph_orchestration("a", [("a", "b")]))

    # Recurses MultiAgentResult -> NodeResult -> AgentResult to reach real text.
    assert extract_text(extract_last_message(result)) != ""
