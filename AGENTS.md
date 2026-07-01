# strands-compose — Agent Instructions

This is **strands-compose**: a declarative multi-agent orchestration library for
[strands-agents](https://github.com/strands-agents/harness-sdk). It reads YAML
configs and returns fully wired, plain `strands` objects — no wrappers, no
subclasses.

---

## Read the Skill First — MANDATORY

Before touching any code, load the skill for the area you are working in. Skills
are the authoritative source for the mental model, conventions, patterns,
dependency rules, and file placement. Everything library-specific lives there,
not here.

| Area | Skill to load |
|------|---------------|
| **Library source** (`src/strands_compose/`) | `.kiro/skills/library-development/SKILL.md` + `.kiro/skills/library-development/references/project-map.md` |

If you work on the library source, read the `library-development` skill. It
describes the target standard — follow it, not whatever pattern happened to be
written before the skill existed.

Two more skills activate automatically and should be used when relevant:

| Skill | Use when |
|-------|----------|
| `.github/skills/strands-api-lookup/SKILL.md` | Working with any strands API — check upstream before implementing |
| `.github/skills/check-and-test/SKILL.md` | Validating, linting, type-checking, or testing |

---

## Core Principles — Apply Everywhere

When in doubt, apply these in order.

1. **Strands-first** — always check what `strands-agents` already provides
   (`.venv/lib/python*/site-packages/strands/`) before implementing anything.
   Use it directly; never re-implement what it exports.
2. **Thin wrapper** — translate YAML to strands objects, then get out of the way.
   Return plain strands objects, never a wrapper or subclass.
3. **Simple over clever** — the dullest solution that correctly solves the
   problem is the right one. Readable and maintainable beats terse.
4. **Transparency over performance** — prefer code that clearly shows what it
   does. Optimize only with measured evidence that it matters.
5. **Explicit over implicit** — no hidden magic, no auto-registration, no global
   singletons. Wire things by hand and make dependencies obvious.
6. **Composition over inheritance** — build big things from small, focused
   pieces that compose.
7. **Single responsibility** — each module, function, and resolver does one
   thing. When something grows a second job, split it.
8. **One-way dependencies** — the pipeline flows one direction; inner layers
   never import outward. The exact direction is defined in the skill.

---

## Behaviour Rules — Apply Everywhere

- **Smallest reasonable change.** Don't refactor unrelated code to land a
  feature. Touch only what the task requires.
- **Read before writing.** Before editing a file, read it. Before creating
  something new, read a sibling that plays the same role and match its shape.
- **No hardcoded secrets.** All credentials and sensitive config come from
  environment variables.
- **Comments explain what and why, never when or how something changed.** No
  temporal context ("recently refactored", "moved from …") in comments.
- **If you find something broken in the area you're working, fix it.** Don't
  leave broken or commented-out code behind.
- **Never add files or change code outside the scope of the task.**
- **Verify before done** — `uv run just check` then `uv run just test` (see the
  `check-and-test` skill).

---

## Path-Specific Instructions

Targeted rules in `.github/instructions/` are applied automatically based on
file paths:

| File | Applies to |
|------|-----------|
| `source.instructions.md` | `src/**/*.py` |
| `tests.instructions.md` | `tests/**/*.py` |
| `examples.instructions.md` | `examples/**/*.py`, `examples/**/*.yaml` |
| `docs.instructions.md` | `docs/**/*.md` |

## Custom Agents

Specialized agents in `.github/agents/` — select the right one for your task:

| Agent | Purpose |
|-------|---------|
| `developer` | Implement features and fix bugs |
| `reviewer` | Review PRs for correctness and compliance (read-only) |
| `tester` | Write and improve tests |
| `docs-writer` | Write and update documentation |
