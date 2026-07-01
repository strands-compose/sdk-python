---
name: library-testing
description: Write, repair, and reason about tests for the strands-compose library in tests/. Use whenever adding, fixing, or reviewing tests, or deciding what to test for a library change. Defines what is worth testing, what is not, and how. Library tests only; not examples or docs prose.
metadata:
  area: testing
  stack: pytest,pytest-asyncio,hypothesis,strands-agents,pydantic-v2
---

# Library Testing

The testing doctrine for the **strands-compose library** (`src/strands_compose/`).
It defines **what is worth testing, what is not, and how**, so the suite stays
small, fast, trustworthy, and cheap to live with. It describes principles and
shapes, not a file list — resolvers, providers, and orchestration modes come and
go, the doctrine stays.

One sentence to internalise: **a test exists to catch a real regression in
behaviour, contract, or wiring — never to mirror the code, freeze its wording,
or re-test strands.** If a test can break when nothing a caller depends on
changed, it is a liability, not an asset.

This library is a **thin translator**: YAML text → validated `*Def` data → live
`strands` objects. That single fact decides everything below. We do not own
`Agent`, `Swarm`, `Graph`, `Model`, `MCPClient`, or strands' hook events — so we
never test them and never mock them. We test **our translation**: that the right
config produces the right wired object, that bad config fails with the right
error, and that our runtime edges (streaming, lifecycle, manifest) behave.

Read `references/test-patterns.md` for the concrete, copy-paste templates (owned
fakes, the resolve-seam patches, config builders, the wiring test, the contract
snapshot, property tests). **This file is the law; that file is the toolbox** —
load the toolbox only when you are actually writing a test.

---

## Core Principles — NON-NEGOTIABLE

1. **Test behaviour, contracts, and wiring — never implementation.** Assert on
   what a caller observes: the *type and wiring* of the returned strands object,
   the raised error *type*, the emitted `StreamEvent` sequence, the manifest
   *shape*. Never on private methods (`_on_*`), private attributes (`_started`,
   `_errored`), mock call counts/order, log lines, or human-readable messages.
2. **Never mock what we don't own.** strands, Pydantic, PyYAML and MCP internals
   are off-limits as mock targets. Substitute a fake at **our** seam (a resolver,
   a factory) — see Mocking Policy. Hand-built `MagicMock` strands events are
   forbidden.
3. **Confidence per line is the metric.** Optimise for the most regressions
   caught per test maintained — not coverage percentage, not test count. A
   smaller suite people trust beats a large one they ignore.
4. **A green suite means "safe to ship"; a red test means "something real
   broke."** Anything that fails for innocuous reasons (a rename, a reorder, a
   reworded message) gets fixed or deleted, not tolerated.
5. **Determinism is mandatory.** No real network, no real model calls, no MCP
   subprocesses, no wall-clock waits, no `sleep`, no shared mutable state, no
   ordering assumptions. Flaky is treated as broken.
6. **Tests are read more than written — favour DAMP over DRY.** Each test reads
   top-to-bottom as a small story: arrange a config, resolve it, assert the
   wiring. Clarity beats cleverness and reuse.
7. **Smallest reasonable test, at the lowest layer that can prove the rule.**
   Pure transform → a unit/property test. Wiring → a resolver test. End-to-end
   shape → one pipeline test. Cover a rule once.

---

## The Shape — What to Test (and how much)

We are an **integration-weighted suite with a fast, pure unit core**, because
the library is mostly glue. Weight effort roughly in this order; let the code
under test decide, not dogma.

- **Resolution / wiring (the core, most tests).** Drive the resolvers and the
  `load` / `resolve_infra` / `load_session` seams against small configs and
  assert the *wiring*: entry is the expected type, the agent got the right
  model/tools/hooks/system-prompt, orchestration topology is correct, the
  session-manager leaf-chain resolves per the rules, the infra-vs-session split
  holds (one `resolve_infra`, many `load_session`, no session manager on infra).
  This is where real bugs live and where tests survive refactors.
- **Schema validation contracts (fast, no strands).** Good config validates;
  bad config raises the **right `ConfigurationError` subclass**
  (`SchemaValidationError`, `UnresolvedReferenceError`, `CircularDependencyError`,
  `ImportResolutionError`). Assert the *type*, never the message text. Cover the
  cross-field validators (entry exists, no name collisions across
  `JOINT_NAMESPACES`, discriminated-union dispatch).
- **Pure transforms (unit + property, fast).** Interpolation (`${VAR:-default}`,
  anchor stripping), key sanitization, relative-path rewriting, source merge,
  reference validation, cycle detection, `load_object` spec parsing. These are
  deterministic functions — test them directly, property-based where a rule
  generalises (see below).
- **Runtime edges (behaviour, per edge).** The `StreamEvent` stream through
  `make_event_queue`; MCP lifecycle ordering and idempotency; `build_manifest`
  introspection. Test the *observable* contract, not the private handlers.
- **The pipeline end-to-end (a thin top layer).** `load()` over real YAML
  fixtures and over every `examples/` config, with strands faked at our seams.
  Asserts the whole flow wires up and the entry object exists — not business
  rules already proven at the resolver layer.
- **The manifest / StreamEvent shape (one snapshot).** A single, deliberate
  contract snapshot guards the introspection/streaming shape against accidental
  drift. Intentional changes are a reviewed diff.

---

## What We DO NOT Test

This list is as important as the one above. Do not write tests that assert on:

- **Private methods or attributes.** `_on_agent_start`, `_on_complete`,
  `_on_tool_start`, `_errored`, `_started`, `_put`, `_callback`. Drive the public
  seam instead and observe the result.
- **Mock interactions.** `registry.add_callback.call_args_list`,
  `mock.assert_called_once_with(...)` on our own internals, call order/counts.
  These freeze implementation, not behaviour. (Asserting a *faked seam* was hit
  is acceptable only when the seam-hit *is* the contract, e.g. lifecycle order.)
- **Log output, warning text, error/exception *messages*, human copy.** Only the
  error *type* is contract. When tempted to assert on a message, assert on the
  **type or state** behind it.
- **strands, Pydantic, PyYAML, MCP behaviour.** `Agent()` storing kwargs,
  `model_dump()`/`model_validate()` round-trips, `json.dumps` output, a `StrEnum`
  member equalling its string, YAML parsing. Trust your dependencies.
- **Trivia and tautologies.** `name in __all__ → hasattr(pkg, name)`,
  field-assignment (`NodeRef(id="x").id == "x"`), enum-value tables, `__repr__`,
  constants, dataclass defaults.
- **Exact event counts / sequences everywhere.** The `StreamEvent` shape is
  pinned **once** in the contract snapshot; elsewhere assert the specific event
  you care about, not `len(events) == 6`.
- **Anything that forces a test edit after a behaviour-preserving refactor.** If
  a refactor that kept behaviour identical breaks a test, the test was wrong.

---

## Folder Structure — MANDATED

`tests/` mirrors the **pipeline stages** (the library's mental model), not the
source file tree. Keep it shallow and predictable; a reader finds the test for a
concern without matching filenames.

```
tests/
├── conftest.py         # root: markers + shared infrastructure fixtures only
├── factories.py        # *Def builders and YAML-string builders (defaults + overrides)
├── fakes/              # hand-written fakes for owned seams
│   └── strands.py          # FakeModel · FakeAgent · FakeMCPServer · FakeMCPClient
├── contract/
│   └── test_shape.py       # the ONE manifest + StreamEvent shape snapshot + baseline
├── property/           # Hypothesis property tests for pure transforms
│   ├── test_interpolation.py
│   ├── test_sanitize_keys.py
│   └── test_merge.py
├── parse/              # loaders/ + interpolation example-based unit tests
├── schema/             # validation contracts — good validates, bad raises typed error
├── resolve/            # *Def -> live object wiring, through public seams (the core)
│   ├── test_agents.py · test_models.py · test_mcp.py
│   ├── test_orchestrations.py · test_session_manager.py · test_hooks.py
├── runtime/            # streaming, lifecycle, manifest behaviour
│   ├── test_event_stream.py · test_mcp_lifecycle.py · test_manifest.py
└── pipeline/           # end-to-end load() (integration marker)
    ├── fixtures/           # small worked YAML configs
    ├── test_load.py        # load() wiring over fixtures
    └── test_examples.py    # every examples/ config loads with faked seams
```

Rules:
- **Mirror the stage, not the file.** `resolve/test_agents.py` covers agent
  wiring regardless of how many source modules it spans. Do not create one test
  file per source file, and never split the same concern across two files (the
  old `test_tools.py` + `test_tools_module.py` split is the anti-pattern).
- **Shared *infrastructure* lives in `conftest.py`; shared *object construction*
  lives in `factories.py`; shared *fakes* live in `fakes/`.** Nothing else is
  shared.
- New stage/concern → the matching folder. Pure logic → `property/` or `parse/`.
- `pipeline/` and anything slow carry the `integration` marker; everything else
  is the fast tier.

---

## Mocking Policy — Fake at Our Seam, Never Mock strands

Our only true external dependencies are the **strands runtime** (model provider
network calls, the MCP subprocess/uvicorn machinery) and **the environment**
(env vars, filesystem). Everything else is our own code and must run for real.

- **Never mock strands or MCP internals directly, and never fabricate strands
  events with `MagicMock`.** Mock at the thin seam *we* own — the resolver or
  factory. The canonical seams to substitute are `resolve_model`,
  `resolve_mcp_server`, `resolve_mcp_client`, and (for streaming) the model that
  drives an `Agent`. Patch them to return a **fake** from `tests/fakes/`.
- **Prefer fakes over `Mock`.** A fake is a real object with a working
  implementation; it survives strands upgrades and reads clearly. A `FakeModel`
  emits a canned event stream; a `FakeMCPServer` records `start`/`wait_ready`/
  `stop`. Reserve `unittest.mock` for forcing hard-to-produce conditions
  (a provider raising, a queue full), and when you must, use `spec_set=` so API
  drift fails loudly.
- **Never mock our own resolvers, loaders, or the objects under test.** Use the
  real `load_config`, real schema, real `load_object`, real wiring. Mocking what
  you are testing tests nothing.
- **Use real strands objects when they are cheap.** A real `Agent` built with a
  `FakeModel` is better than a mocked one — it proves our kwargs are actually
  accepted by the current strands API. This is how we catch upstream drift.
- If a strands object is hard to fake, that is a signal our seam around it is too
  thin — fix the seam, don't bury strands in test boilerplate.

---

## Strands & Environment Strategy — Fidelity Where It Counts

- **Default to real objects through the public seams.** Resolver and pipeline
  tests build real `*Def` models and call the real resolver / `load`; only the
  provider network call and MCP process are faked.
- **The provider seam is the fake boundary.** `resolve_model` → `FakeModel`
  keeps us off the network while exercising every line of our own agent/model
  wiring. Never reach past it into a provider SDK.
- **MCP is faked at the server/client factory.** Assert the *observable* order
  contract (servers ready before clients connect, clients stop before servers,
  `start()` idempotent) via the fake's recorded calls — never via `_started`.
- **Filesystem via `tmp_path`; env via `monkeypatch.setenv`.** Never touch the
  real home dir, real `~/.aws`, or real network. Never rely on ambient env.
- **Streaming is deterministic.** A `FakeModel` yields a fixed event list;
  assert the `StreamEvent`s that come out of `make_event_queue`. No timing waits.

---

## Test Data — Builders, Not Fixture Sprawl

- **Use builder functions in `factories.py`** that construct `*Def` models or
  YAML strings with sensible defaults and accept overrides for only the fields
  the test cares about: `agent_def(model="fast")`, `app_config(entry="a")`,
  `yaml_config(agents={...})`. This keeps each test's *relevant* inputs visible
  and the irrelevant ones out of sight.
- **Avoid the giant `conftest` fixture web** and ever-growing god-helpers. A
  fixture is justified only for genuine shared *infrastructure* (the fakes, a
  fixtures-dir resolver), not for business objects.
- **DAMP, not DRY, inside a test.** Inline the arrange step that tells the story.
  Don't hide it behind loops, multi-level helpers, or `setUp` magic the reader
  must chase. Light duplication across tests is fine and expected.

---

## Property-Based Testing (Hypothesis) — Targeted

Use it where a rule must hold across a domain of inputs, not for example-by-
example checks. Strong fits here, all in the pure parse layer:

- **Key sanitization** always yields `[a-zA-Z0-9_-]`, is idempotent, and keeps
  internal references consistent after rewriting.
- **Interpolation**: `${VAR:-default}` resolves to the env value when set and the
  default when not; text with no placeholders is unchanged; interpolation is a
  fixed point (running it twice changes nothing).
- **Merge**: merging disjoint sources is order-independent for the result set and
  **always** raises on a duplicate name.

Keep generators tight and assert the **invariant**, not a re-computation of the
implementation. Property tests complement unit and wiring tests; they do not
replace the contract or pipeline tests.

---

## Coverage & Mutation — Signal, Not Theatre

- **Coverage is a floor and a gap-finder, never a goal.** A high number with
  weak assertions is false confidence. Tests that execute lines without asserting
  are forbidden. Do not chase 100%, and do not add a test purely to move the
  number. The `≥70%` gate is a safety net, not the definition of done.
- **Assertion quality is the real signal.** For the modules that matter most —
  `config/schema.py` validators, `config/loaders/validators.py`, the resolvers,
  `utils.load_object`, `config/interpolation.py` — validate the suite with
  **mutation testing** periodically (e.g. `mutmut`). If a deliberately broken
  operator still passes, an assertion is missing. Treat surviving mutants, not
  uncovered lines, as the to-do list.

---

## Conventions

- **`from __future__ import annotations`** at the top of every test module.
- **Name states behaviour + expectation:** `test_missing_model_ref_raises_unresolved_reference`,
  not `test_model`. The name reads as a sentence and does not just echo the
  function under test.
- **Arrange-Act-Assert**, visibly separated. One logical behaviour per test; one
  reason to fail.
- **`pytest.raises` asserts the type; `match=` targets a stable token, never a
  full sentence.** Match a config name or identifier that is part of the
  contract, not prose that may be reworded.
- **Parametrize** equivalent cases instead of copy-pasting near-identical bodies;
  keep each case independently named/identifiable.
- **Async:** `pytest-asyncio` auto mode is on. Use async fakes and never block
  the loop or sleep.
- Typed signatures; per-file test ignores (`D`, `ANN`, `S101`) are already
  configured — keep tests readable, not ceremony-heavy.
- **Run with `uv run just test`** (never bare `pytest`); use `uv run pytest <path>`
  for fast local iteration on one file.

---

## Adding or Repairing a Test — Checklist

1. **Name the behaviour** you're protecting in one sentence. If you can't, you
   probably shouldn't write the test.
2. **Pick the lowest layer** that proves it: pure transform → `property/` or
   `parse/`; validation → `schema/`; `*Def` → object → `resolve/`; runtime edge
   → `runtime/`; whole flow → `pipeline/`.
3. **Read a sibling test first** and mirror its shape, naming, factories, and
   fakes.
4. **Use real code through the public seam; fake only strands at our resolver
   seam.** Real `load_config`, real schema, real `load_object`.
5. **Assert on type / wiring / shape / emitted event — never on text, private
   members, or mock calls.**
6. **When a test breaks after a refactor:** first ask *did behaviour change?* If
   no, the test was over-specified — fix or delete it, don't contort the code. If
   yes, the test did its job — update the expectation.
7. **Verify** before declaring done: `uv run just check` then `uv run just test`.

---

## Anti-Patterns — Do NOT

- Call private handlers (`_on_*`) or read private state (`_started`, `_errored`)
  to make an assertion; drive the public seam and observe the output.
- Fabricate strands events with `MagicMock` / `SimpleNamespace`, or patch
  `Agent.__init__` — build a real `Agent` with a `FakeModel`, or fake the
  resolver seam.
- Mock strands, Pydantic, PyYAML, MCP, or our own resolvers/loaders/SUT.
- Assert on log messages, exception *text*, or response wording (type only).
- Assert `len(events) == N` or a full event sequence outside the one contract
  snapshot.
- Test Pydantic (`model_dump`, field assignment), `StrEnum` values, or `__all__`
  as standalone tests.
- Build one test file per source file, or split one concern across two files.
- Add a test that only raises the coverage number, or a test with no assertion.
- Hide a test's arrange step behind clever helpers, loops, or `setUp` magic.
- Use `sleep`, real clocks, real network, real model calls, MCP subprocesses,
  unseeded randomness, or cross-test shared state.
- Snapshot anything other than the single, deliberate manifest/StreamEvent shape.
- Leave a flaky test "for later" — quarantine and fix, or delete.
