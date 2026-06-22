# run test tasks
[group('test')]
test: test-coverage

# check code coverage
[group('test')]
test-coverage cov_fail_under="90":
    uv run python -m pytest --numprocesses=2 --cov={{SOURCES}} --cov-fail-under={{cov_fail_under}} {{TESTS}}

# run mutation testing (requires: pip install mutmut)
[group('test')]
test-mutation module="src/strands_compose/hooks/event_publisher.py":
    uv run mutmut run --paths-to-mutate={{module}} --tests-dir={{TESTS}} --runner="python -m pytest -x -q"
