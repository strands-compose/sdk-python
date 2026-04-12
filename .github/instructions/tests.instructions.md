---
applyTo: "tests/**/*.py"
---

# Test Code Instructions

All Python rules from `AGENTS.md` apply. Additional rules for test files:

- `from __future__ import annotations` at the top of every test module.
- Name tests descriptively: `test_<what>_<condition>_<expected_outcome>`.
- Test **behaviour**, not implementation details.
- One `assert` concept per test where practical.
- Use `pytest.raises` with `match=` for exception tests.
- Mock at the boundary: patch I/O, network, and strands internals — not internal logic.
- Use `tmp_path` for file system interactions.
- Parametrize repetitive cases instead of copy-pasting test bodies.
- Run tests with `uv run just test` — never bare `pytest`.
- In edge cases use `uv run pytest ...` for faster iteration.
- Coverage must remain ≥ 70%.
