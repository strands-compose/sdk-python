---
applyTo: "docs/**/*.md"
---

# Documentation Instructions

- Use plain English. Short sentences. Active voice.
- Show `uv run` in all command examples — never bare `python`, `pip`, or `pytest`.
- Every documented feature needs a minimal working YAML example.
- YAML examples must use valid strands-compose syntax — verify against the JSON schema in `src/strands_compose/config/schema.py`.
- Python examples must be runnable as-is with `uv run python`.
- Do not document internal implementation details — only the public API and YAML config surface.
- Use relative links for files within the repository (never absolute URLs).
- Keep content consistent with `AGENTS.md` rules and the Key APIs table.
