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
| **Library tests** (`tests/`) | `.kiro/skills/library-testing/SKILL.md` + `.kiro/skills/library-testing/references/test-patterns.md` |

If you work on the library source, read the `library-development` skill; if you
work on tests, read the `library-testing` skill. They describe the target
standard — follow it, not whatever pattern happened to be written before the
skill existed.

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
