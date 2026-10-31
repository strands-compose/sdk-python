"""Owned fakes standing in for the strands runtime.

These let tests drive real ``strands.Agent`` / ``Swarm`` / ``Graph`` objects and
the real event loop without a provider network call or an MCP subprocess. They
are the single fake boundary — see the ``library-testing`` skill's Mocking
Policy. Never fabricate strands hook events with ``MagicMock``; build a real
agent around one of these models instead.
"""

from __future__ import annotations

from typing import Any

from strands import tool
from strands.models import Model
from strands.plugins import Plugin
from strands.types.exceptions import ModelThrottledException


class FakeModel(Model):
    """A strands ``Model`` that streams a fixed text response, no network.

    Drives the real strands event loop, so a real ``Agent`` built with this
    model emits genuine AGENT_START / TOKEN / AGENT_COMPLETE activity through
    ``EventPublisher``.
    """

    def __init__(
        self,
        text_chunks: list[str] | None = None,
        *,
        model_id: str = "fake-model",
        usage: dict[str, int] | None = None,
        reasoning_chunks: list[str] | None = None,
    ) -> None:
        """Store the chunks to stream, a model id and the usage to report."""
        self._text_chunks = text_chunks if text_chunks is not None else ["Hello", " world"]
        self._config: dict[str, Any] = {"model_id": model_id}
        self._usage = usage or {"inputTokens": 5, "outputTokens": 3, "totalTokens": 8}
        self._reasoning_chunks = reasoning_chunks or []

    def update_config(self, **model_config: Any) -> None:
        """Merge overrides into the reported config."""
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        """Return the reported config (used by the manifest model descriptor)."""
        return self._config

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ):
        """Yield a single empty structured-output instance (unused by most tests)."""
        yield {"output": output_model()}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ):
        """Stream a minimal text completion in the raw strands chunk protocol."""
        yield {"messageStart": {"role": "assistant"}}
        if self._reasoning_chunks:
            yield {"contentBlockStart": {"start": {}}}
            for chunk in self._reasoning_chunks:
                yield {"contentBlockDelta": {"delta": {"reasoningContent": {"text": chunk}}}}
            yield {"contentBlockStop": {}}
        yield {"contentBlockStart": {"start": {}}}
        for chunk in self._text_chunks:
            yield {"contentBlockDelta": {"delta": {"text": chunk}}}
        yield {"contentBlockStop": {}}
        yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": self._usage, "metrics": {"latencyMs": 1}}}


class ToolThenTextModel(Model):
    """Streams one tool call on the first turn, then a text answer on the second."""

    def __init__(self, *, tool_name: str, tool_input: str = '{"name": "Bob"}') -> None:
        """Store the tool to call on the first turn."""
        self._config: dict[str, Any] = {"model_id": "fake-tool-model"}
        self._tool_name = tool_name
        self._tool_input = tool_input
        self._turn = 0

    def update_config(self, **model_config: Any) -> None:
        """Merge overrides into the reported config."""
        self._config.update(model_config)

    def get_config(self) -> dict[str, Any]:
        """Return the reported config."""
        return self._config

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ):
        """Yield a single empty structured-output instance (unused)."""
        yield {"output": output_model()}

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ):
        """First turn: call the tool. Second turn: emit text and stop."""
        self._turn += 1
        yield {"messageStart": {"role": "assistant"}}
        if self._turn == 1:
            yield {
                "contentBlockStart": {
                    "start": {"toolUse": {"name": self._tool_name, "toolUseId": "call-1"}}
                }
            }
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": self._tool_input}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            yield {"contentBlockDelta": {"delta": {"text": "Done"}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {
            "metadata": {
                "usage": {"inputTokens": 1, "outputTokens": 1, "totalTokens": 2},
                "metrics": {"latencyMs": 1},
            }
        }


class BoomModel(Model):
    """A model whose stream raises, to drive the ERROR event path."""

    def __init__(self, *, message: str = "credentials expired") -> None:
        """Store the failure message the model call raises with."""
        self._message = message

    def update_config(self, **model_config: Any) -> None:
        """No-op — this model never succeeds."""

    def get_config(self) -> dict[str, Any]:
        """Return a minimal config."""
        return {"model_id": "boom-model"}

    async def structured_output(
        self, output_model: Any, prompt: Any, system_prompt: Any = None, **kwargs: Any
    ):
        """Raise on structured output too."""
        raise RuntimeError(self._message)
        yield  # pragma: no cover — makes this an async generator

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ):
        """Raise a provider-style error mid-call."""
        raise RuntimeError(self._message)
        yield  # pragma: no cover — makes this an async generator


class FlakyOnceModel(FakeModel):
    """Throttles on the first ``stream`` call, then behaves like :class:`FakeModel`.

    Drives strands' model retry path: a retry strategy recovers the invocation.
    """

    def __init__(self, text_chunks: list[str] | None = None) -> None:
        """Store the text to stream once the throttled first call is retried."""
        super().__init__(text_chunks, model_id="flaky-model")
        self._failed_once = False

    async def stream(
        self, messages: Any, tool_specs: Any = None, system_prompt: Any = None, **kwargs: Any
    ):
        """Raise ``ModelThrottledException`` once, then stream normally."""
        if not self._failed_once:
            self._failed_once = True
            raise ModelThrottledException("throttled")
        async for chunk in super().stream(messages, tool_specs, system_prompt, **kwargs):
            yield chunk


class FakePlugin(Plugin):
    """Minimal Plugin that contributes one identifiable ``@tool``.

    ``prefix`` lets a test tell instances apart and appears in the tool result.
    """

    name = "fake-plugin"

    def __init__(self, *, prefix: str = "") -> None:
        super().__init__()
        self.prefix = prefix

    @tool  # type: ignore[misc]
    def fake_plugin_tool(self) -> str:
        """Signal that the fake plugin is wired."""
        return f"{self.prefix}ok"


def fake_plugin_factory(*, prefix: str = "") -> FakePlugin:
    """Return a :class:`FakePlugin` — the callable path of plugin resolution."""
    return FakePlugin(prefix=prefix)


class FakeMCPClient:
    """Minimal MCP client stand-in — contributes no tools, hits no network."""

    def __init__(self) -> None:
        """Initialise an empty call log."""
        self.calls: list[str] = []

    def start(self) -> None:
        """Record a start."""
        self.calls.append("start")

    def stop(self, exc_type: Any = None, exc_val: Any = None, exc_tb: Any = None) -> None:
        """Record a stop (matches the strands MCPClient stop signature)."""
        self.calls.append("stop")
