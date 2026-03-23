# bump package version
[group('commit')]
commit-bump:
    uv run cz bump

# commit package with commitizen
[group('commit')]
commit-files:
    uv run cz commit

# get commit info
[group('commit')]
commit-info:
    uv run cz info

# run pre-commit hooks on all files
[group('commit')]
check-hooks:
    uv run pre-commit run --all-files
