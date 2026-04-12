---
applyTo: "src/**/*.py"
---

# Source Code Instructions

All Python rules from `AGENTS.md` apply. Key reminders for source files:

- Execute with `uv run python script.py` — never bare `python`.
- `from __future__ import annotations` at the top of every module.
- Full type annotations on all public functions (parameters + return type).
- Use `X | None`, `list`, `dict` — never `Optional`, `Union`, `List`, `Dict`.
- Google-style docstring on every public class, function, and method. Class docstrings go on `__init__`.
- Structured logging with `%s` and field-value pairs — never f-strings in `logger.*` calls.
- Check `.venv/lib/python*/site-packages/strands/` before implementing — do NOT reimplement upstream functionality.
- Run `uv run just check` and `uv run just test` before committing.
