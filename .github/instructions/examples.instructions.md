---
applyTo: "examples/**/*.py,examples/**/*.yaml"
---

# Example Code Instructions

Examples must be complete, runnable, and easy to understand.

- Every example directory needs `config.yaml`, `main.py`, and `README.md`.
- Python files must be runnable as-is with `uv run python examples/NN_name/main.py`.
- YAML files must use valid strands-compose syntax.
- Show `uv run` in all command examples — never bare `python` or `pip`.
- Keep examples minimal — demonstrate one concept per example.
- Do not import private/internal APIs — only use the public API from `strands_compose`.
- Use `examples/TEMPLATE_EXAMPLE.md` as a structural guide for new examples.
