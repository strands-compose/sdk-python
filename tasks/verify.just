# run the checks without changing any file (CI runs this)
[group('verify')]
verify: verify-format verify-code check-type check-security

# verify code quality without changing any file (pyproject sets ruff fix = true)
[group('verify')]
verify-code:
    uv run ruff check --no-fix {{SOURCES}} {{TESTS}} {{EXAMPLES}}

# verify import order and code format without changing any file
[group('verify')]
verify-format:
    uv run ruff check --select=I --no-fix {{SOURCES}} {{TESTS}} {{EXAMPLES}}
    uv run ruff format --check {{SOURCES}} {{TESTS}} {{EXAMPLES}}
