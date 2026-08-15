# Project Tasks

This directory contains Just tasks for automating common project operations. Each task file is focused on a specific aspect of the project.

## Task Groups

### Check Tasks (`check.just`)
Tasks for running code quality checks:

- `check`: Run all checks (format + code + type + security)
  ```bash
  uv run just check
  ```

- `check-format`: Check code formatting (import order + ruff format)
  ```bash
  uv run just check-format
  ```

- `check-code`: Run linting checks (ruff check)
  ```bash
  uv run just check-code
  ```

- `check-type`: Run type checking (ty)
  ```bash
  uv run just check-type
  ```

- `check-security`: Run security scan (bandit)
  ```bash
  uv run just check-security
  ```

- `check-test`: Run unit tests (pytest)
  ```bash
  uv run just check-test
  ```

- `check-hooks`: Run all pre-commit hooks on all files
  ```bash
  uv run just check-hooks
  ```

### Clean Tasks (`clean.just`)
Tasks for cleaning project files and caches:

- `clean`: Run all clean tasks
  ```bash
  uv run just clean
  ```

- `clean-build`: Clean build folders (dist, build)
  ```bash
  uv run just clean-build
  ```

- `clean-cache`: Clean .cache directory
  ```bash
  uv run just clean-cache
  ```

- `clean-constraints`: Clean constraints.txt
  ```bash
  uv run just clean-constraints
  ```

- `clean-coverage`: Clean .coverage files
  ```bash
  uv run just clean-coverage
  ```

- `clean-ty`: Clean ty cache
  ```bash
  uv run just clean-ty
  ```

- `clean-pytest`: Clean pytest cache
  ```bash
  uv run just clean-pytest
  ```

- `clean-python`: Clean Python caches (__pycache__ and .pyc/.pyo files)
  ```bash
  uv run just clean-python
  ```

- `clean-requirements`: Clean requirements.txt
  ```bash
  uv run just clean-requirements
  ```

- `clean-ruff`: Clean ruff cache
  ```bash
  uv run just clean-ruff
  ```

- `clean-venv`: Clean virtual environment (requires confirmation)
  ```bash
  uv run just clean-venv
  ```

### Commit Tasks (`commit.just`)
Tasks for managing commits:

- `commit-bump`: Bump the package version using Commitizen
  ```bash
  uv run just commit-bump
  ```

- `commit-files`: Create a conventional commit using Commitizen
  ```bash
  uv run just commit-files
  ```

- `commit-info`: Retrieve commit information using Commitizen
  ```bash
  uv run just commit-info
  ```

### Format Tasks (`format.just`)
Tasks for code formatting:

- `format`: Run all format tasks (import + source)
  ```bash
  uv run just format
  ```

- `format-import`: Format import order (ruff check --select=I --fix)
  ```bash
  uv run just format-import
  ```

- `format-source`: Format source code (ruff format)
  ```bash
  uv run just format-source
  ```

### Install Tasks (`install.just`)
Tasks for managing dependencies:

- `install`: Install all dependencies **and** wire git hooks (run this after every fresh clone)
  ```bash
  uv run just install
  ```

- `install-project`: Install Python dependencies only (no hooks)
  ```bash
  uv run just install-project
  ```

- `install-hooks`: Register pre-commit hooks into `.git/hooks/` (pre-commit, pre-push, commit-msg)
  ```bash
  uv run just install-hooks
  ```

### Release Tasks (`release.just`)
Tasks for releasing the package:

- `release-dry`: Preview the next version bump (no changes written)
  ```bash
  uv run just release-dry
  ```

- `release`: Bump version, update CHANGELOG, and create a git tag
  ```bash
  uv run just release
  ```

- `release-build`: Build distribution artifacts locally
  ```bash
  uv run just release-build
  ```

- `release-test-publish`: Publish to TestPyPI (dry-run against the test registry)
  ```bash
  uv run just release-test-publish
  ```

- `release-next`: Show the next version that commitizen would pick
  ```bash
  uv run just release-next
  ```

### Test Tasks (`test.just`)
Tasks for running tests:

- `test`: Run all test tasks (coverage)
  ```bash
  uv run just test
  ```

- `test-coverage`: Run tests with coverage (80% threshold by default)
  ```bash
  uv run just test-coverage
  ```

- `test-mutation`: Run mutation testing on a module (requires mutmut)
  ```bash
  uv run just test-mutation
  ```

## Usage

1. Install Just:
   ```bash
   # On Ubuntu/Debian
   sudo apt install just

   # On macOS
   brew install just
   ```

2. Run tasks:
   ```bash
   uv run just <task-name>
   ```

3. List all available tasks:
   ```bash
   uv run just --list
   ```

4. Get help for a specific task:
   ```bash
   uv run just <task-name> --help
   ```

## Task Dependencies

Some tasks depend on others. For example:
- `clean` runs all clean tasks
- `check` runs all check tasks (check-format, check-code, check-type, check-security)
- `format` runs all format tasks (format-import, format-source)
- `test` runs test-coverage
- `release` depends on check and test
