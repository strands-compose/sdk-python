---
name: check-and-test
description: Run lint, type checks, security scan, and tests for strands-compose. Use this when asked to validate, check, lint, test, or verify code quality.
---

# Check and Test

Run the full validation pipeline before committing or opening a PR.

## Steps

1. Run lint, type check, and security scan:

```bash
uv run just check
```

2. If `check` fails, auto-format first and re-run:

```bash
uv run just format
uv run just check
```

3. Run the test suite with coverage:

```bash
uv run just test
```

4. If a specific test fails, run it in isolation for faster debugging:

```bash
uv run pytest tests/unit/hooks/test_stop_guard.py -x -v
uv run pytest -k "test_name" -x -v
```

## Coverage

Coverage must remain **≥ 70%**. If coverage drops, add tests for the uncovered code before proceeding.

## Troubleshooting

- **Import errors**: Run `uv sync --all-groups --all-extras` to sync dependencies.
- **Type errors**: Check for missing `from __future__ import annotations` at the top of the module.
- **Lint errors**: Run `uv run just format` first — it fixes most style issues automatically.
