# Test Patterns — the toolbox

Concrete, copy-paste templates for the doctrine in `SKILL.md`. Load this only
when actually writing a test. Exact names drift — trust the **shapes** and adapt
to the current public API (`strands_compose/__init__.py`) and pipeline
(`config/loaders/loaders.py`).

Everything here obeys two rules from the law: **fake strands at our own resolver
seam**, and **assert on wiring / type / emitted event — never on private members,
mock calls, or message text.**

---

## 1. Owned fakes — `tests/fakes/strands.py`

One authoritative fake per external seam. These stand in for the strands runtime
so tests never hit a network, a provider SDK, or an MCP subprocess.

```python
from __future__ import annotations

from collections.abc import Callable


class FakeModel:
    """Stands in for a strands Model. Drives an Agent without a provider call.

    Emits a fixed callback-handler event stream so streaming tests are
    deterministic. Extend the stream shape to match what the code under test
    reads from strands' callback handler.
    """

    def __init__(self, events: list[dict] | None = None) -> None:
        self._events = events or [{"data": "Hello"}]
        self.config: dict = {}

    def stream(self, *args, **kwargs):
        for event in self._events:
            yield event


class FakeMCPServer:
    """Records lifecycle calls; asserts ordering/idempotency without a real server."""

    def __init__(self) -> None:
        self.calls: list[str] = []
        self.started = False

    def start(self) -> None:
        self.calls.append("start")
        self.started = True

    def wait_ready(self, timeout: float) -> bool:
        self.calls.append("wait_ready")
        return True

    def stop(self) -> None:
        self.calls.append("stop")
        self.started = False


class FakeMCPClient:
    """Minimal MCP client stand-in for lifecycle tests."""

    def __init__(self) -> None:
        self.calls: list[str] = []

    def start(self) -> None:
        self.calls.append("start")

    def stop(self, exc_type=None, exc_val=None, exc_tb=None) -> None:
        self.calls.append("stop")
```

Prefer a **real** `strands.Agent` built with a `FakeModel` over a fake agent —
it proves our constructor kwargs match the installed strands API. Only fake the
agent when construction is genuinely too costly for the test's purpose.

---

## 2. Faking the resolve seams — the patch boundary

Patch **our** resolvers, not strands. The seams live where `resolve_infra` /
`load_session` call them, so patch them there (patch where used, not where
defined).

```python
from unittest.mock import patch

from tests.fakes.strands import FakeMCPClient, FakeMCPServer, FakeModel


def fake_runtime():
    """Context managers that swap the strands-facing seams for fakes."""
    return (
        patch(
            "strands_compose.config.resolvers.config.resolve_model",
            lambda model_def: FakeModel(),
        ),
        patch(
            "strands_compose.config.resolvers.config.resolve_mcp_server",
            lambda *a, **k: FakeMCPServer(),
        ),
        patch(
            "strands_compose.config.resolvers.config.resolve_mcp_client",
            lambda *a, **k: FakeMCPClient(),
        ),
    )
```

A pytest fixture wrapping these belongs in `conftest.py` if many tests need it.
Keep the patch targets pointing at the module that *uses* the symbol.

---

## 3. Config builders — `tests/factories.py`

Builders make the *relevant* inputs visible and hide the rest. Provide both a
`*Def`/`AppConfig` builder (for schema + resolver tests) and a YAML-string
builder (for parse + pipeline tests).

```python
from __future__ import annotations

import textwrap

from strands_compose.config.schema import AgentDef, AppConfig


def agent_def(**overrides) -> AgentDef:
    defaults = {"system_prompt": "You are a test agent."}
    return AgentDef(**{**defaults, **overrides})


def app_config(**overrides) -> AppConfig:
    """A minimal valid AppConfig: one agent, entry set. Override any field."""
    agents = overrides.pop("agents", {"assistant": agent_def()})
    entry = overrides.pop("entry", "assistant")
    return AppConfig(agents=agents, entry=entry, **overrides)


def yaml_config(body: str) -> str:
    """Dedent a YAML literal for parse/pipeline tests written against tmp files."""
    return textwrap.dedent(body)
```

Write to disk with `tmp_path` when a test needs a real file path:

```python
def write_config(tmp_path, body: str):
    path = tmp_path / "config.yaml"
    path.write_text(yaml_config(body))
    return path
```

---

## 4. Resolver wiring test — the core template

Build a real `*Def`, resolve through the real seam with strands faked, assert on
the **wiring** of the returned object. No private access.

```python
from __future__ import annotations

from strands import Agent

from strands_compose.config import load_config, resolve_infra, load_session
from tests.factories import app_config, agent_def


def test_agent_receives_configured_model_and_prompt(fake_runtime):
    config = app_config(
        models={"fast": ...},                       # a valid ModelDef
        agents={"a": agent_def(model="fast", system_prompt="Be terse.")},
        entry="a",
    )
    with fake_runtime:
        infra = resolve_infra(config)
        resolved = load_session(config, infra)

    entry = resolved.entry
    assert isinstance(entry, Agent)                 # correct *type* of wired object
    assert entry.system_prompt == "Be terse."       # correct wiring, observable
    # do NOT assert on how resolve_model was called, or on private agent state
```

For orchestrations, assert topology through the public result:

```python
def test_delegate_entry_is_the_orchestrator(fixture_path):
    resolved = load(fixture_path("multi_agent_delegate.yaml"))
    assert resolved.entry is resolved.orchestrators["coordinator"]
    assert "researcher" in resolved.agents
```

---

## 5. Schema contract test — typed error, not text

Good config validates; bad config raises the **right subclass**. Match a stable
identifier, never a sentence.

```python
import pytest

from strands_compose.config.loaders.validators import validate_references
from strands_compose.exceptions import UnresolvedReferenceError
from tests.factories import app_config, agent_def


def test_missing_model_ref_raises_unresolved_reference():
    config = app_config(agents={"a": agent_def(model="ghost")}, entry="a")
    with pytest.raises(UnresolvedReferenceError, match="ghost"):  # the ref name is contract
        validate_references(config)
```

Cycle detection follows the same shape, raising `CircularDependencyError`.
Discriminated-union / cross-field rules raise `SchemaValidationError` (or a
Pydantic `ValidationError` surfaced as one) — assert the *type*.

---

## 6. StreamEvent contract — through `make_event_queue`

Test the emitted event stream via the public seam, driven by a `FakeModel`.
Never call `pub._on_*` and never fabricate strands hook events.

```python
from strands import Agent

from strands_compose.wire import make_event_queue
from strands_compose.types import EventType
from tests.fakes.strands import FakeModel


async def test_text_response_emits_token_events():
    agent = Agent(model=FakeModel(events=[{"data": "Hello"}, {"data": " world"}]))
    queue = make_event_queue(agent, agent_name="assistant")

    # run the agent through the public API; collect what the consumer sees
    events = await drain(queue)  # helper: await queue.get() until None

    kinds = [e.type for e in events]
    assert EventType.SESSION_START == kinds[0]
    assert EventType.SESSION_END == kinds[-1]
    assert any(e.type == EventType.TOKEN and e.data["text"] == "Hello" for e in events)
    # assert the specific event you care about — NOT len(events) == N
```

If a real `Agent` run is impractical for a given edge, attach `EventPublisher`
through `make_event_queue` and feed it **real** strands hook-event objects
imported from `strands.hooks.events` — never `MagicMock` substitutes.

---

## 7. The single contract snapshot — `tests/contract/test_shape.py`

Exactly one deliberate snapshot for the introspection/streaming *shape*. A diff
is a reviewed decision, not a surprise.

```python
import json
from pathlib import Path

from strands_compose.types import StreamEvent, SessionManifest

BASELINE = Path(__file__).parent / "shape_baseline.json"


def test_public_shape_is_stable():
    shape = {
        "stream_event": sorted(StreamEvent.model_fields),
        "session_manifest": sorted(SessionManifest.model_fields),
        # add the manifest sub-models' field names here
    }
    expected = json.loads(BASELINE.read_text())
    assert shape == expected  # regenerate the baseline only on an intended change
```

This replaces scattered `len(events) == 6` / exact-sequence assertions and the
enum-value tables. Keep it to field *names/shape*, not values.

---

## 8. Property tests — `tests/property/`

Assert invariants over a domain, not recomputations. Keep strategies tight.

```python
from hypothesis import given, strategies as st

from strands_compose.config.loaders.helpers import sanitize_collection_keys  # adapt name


@given(st.text(min_size=1, max_size=40))
def test_sanitized_key_is_always_safe(raw):
    safe = sanitize_key(raw)
    assert all(c.isalnum() or c in "-_" for c in safe)
    assert sanitize_key(safe) == safe            # idempotent
```

```python
from hypothesis import given, strategies as st


@given(st.text(), st.text(min_size=1))
def test_default_used_only_when_var_unset(default, name, monkeypatch):
    monkeypatch.delenv(name, raising=False)
    assert interpolate(f"${{{name}:-{default}}}") == default
    monkeypatch.setenv(name, "SET")
    assert interpolate(f"${{{name}:-{default}}}") == "SET"
```

Merge invariant: merging disjoint sources yields the union; a duplicate name
**always** raises — assert both.

---

## 9. MCP lifecycle ordering — via the fake, observable only

Assert the *contract* (order + idempotency) through the fake's recorded calls.
Never read `lifecycle._started`.

```python
from strands_compose.mcp.lifecycle import MCPLifecycle
from tests.fakes.strands import FakeMCPServer


def test_start_is_idempotent_and_starts_server_once():
    lc = MCPLifecycle()
    server = FakeMCPServer()
    lc.add_server("s", server)

    lc.start()
    lc.start()                      # idempotent

    assert server.calls.count("start") == 1
    assert "wait_ready" in server.calls   # ready before use — the observable order
```

For concurrency, spawn real threads calling `start()`, then assert the fake saw
exactly one `start` — the observable idempotency contract, not a private flag.

---

## 10. Pipeline & examples — the thin top layer

```python
import pytest
from strands import Agent

from strands_compose.config import ResolvedConfig, load


@pytest.mark.integration
def test_minimal_pipeline_wires_entry_agent(fixture_path):
    resolved = load(fixture_path("minimal.yaml"))
    assert isinstance(resolved, ResolvedConfig)
    assert isinstance(resolved.entry, Agent)
```

Every `examples/` config gets loaded once, parametrized by directory, with the
runtime seams faked (see pattern 2). This is a smoke/wiring guard — assert the
result is a `ResolvedConfig` with a non-None entry, then `stop()` the lifecycle.
Do not assert business rules here; those are proven in `resolve/`.

---

## Quick decision guide

| I'm testing… | Layer | Fake? | Assert on |
|--------------|-------|-------|-----------|
| a pure text/dict transform | `property/` or `parse/` | nothing | invariant / value |
| good vs bad config | `schema/` | nothing | error **type** |
| a `*Def` → live object | `resolve/` | strands at resolver seam | **type + wiring** |
| the event stream | `runtime/` | `FakeModel` | emitted `StreamEvent` |
| MCP start/stop order | `runtime/` | `FakeMCPServer/Client` | recorded call order |
| the whole flow | `pipeline/` | all runtime seams | `ResolvedConfig` + entry |
| the public shape | `contract/` | nothing | field names (snapshot) |
