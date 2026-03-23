# run check tasks
[group('check')]
check: check-format check-code check-type check-security

# check code quality
[group('check')]
check-code:
    uv run ruff check {{SOURCES}} {{TESTS}} {{EXAMPLES}}

# check code format
[group('check')]
check-format:
    uv run ruff check --select=I --fix {{SOURCES}} {{TESTS}} {{EXAMPLES}}
    uv run ruff format {{SOURCES}} {{TESTS}} {{EXAMPLES}}
    uv run ruff format --check {{SOURCES}} {{TESTS}} {{EXAMPLES}}

# check code security
[group('check')]
check-security:
    uv run python -m bandit --recursive --configfile=pyproject.toml {{SOURCES}} {{EXAMPLES}}

# check unit tests
[group('check')]
check-test numprocesses="auto":
    uv run python -m pytest --numprocesses={{numprocesses}} {{TESTS}}

# check code typing
[group('check')]
check-type:
    uv run ty check {{SOURCES}} {{TESTS}} {{EXAMPLES}}
