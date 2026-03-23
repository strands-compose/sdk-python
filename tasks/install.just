# install git hooks
[group('install')]
install-hooks:
    uv run pre-commit install
    uv run pre-commit install --hook-type=pre-push
    uv run pre-commit install --hook-type=commit-msg

# install the project
[group('install')]
install-project:
    uv sync --all-groups --all-extras

# run install tasks
[group('install')]
install: install-project install-hooks
