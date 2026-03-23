# Project Tasks

This directory contains Just tasks for automating common project operations. Each task file is focused on a specific aspect of the project.

## Task Groups

### Clean Tasks (`clean.just`)
Tasks for cleaning project files and caches:

- `clean`: Run all clean tasks
  ```bash
  uv run just clean
  ```

- `clean-python`: Clean Python cache files (in src, tests, notebooks)
  ```bash
  uv run just clean-python
  ```

- `clean-cache`: Clean .cache directory
  ```bash
  uv run just clean-cache
  ```

- `clean-ty`: Clean ty cache
  ```bash
  uv run just clean-ty
  ```

- `clean-pytest`: Clean pytest cache
  ```bash
  uv run just clean-pytest
  ```

- `clean-ruff`: Clean ruff cache
  ```bash
  uv run just clean-ruff
  ```

- `clean-venv`: Clean virtual environment (requires confirmation)
  ```bash
  uv run just clean-venv
  ```

### Check Tasks (`check.just`)
Tasks for running code quality checks:

- `check`: Run all checks
  ```bash
  uv run just check
  ```

- `check-lint`: Run linting checks
  ```bash
  uv run just check-lint
  ```

- `check-type`: Run type checking
  ```bash
  uv run just check-type
  ```

- `check-test`: Run tests
  ```bash
  uv run just check-test
  ```

### Format Tasks (`format.just`)
Tasks for code formatting:

- `format`: Format all code
  ```bash
  uv run just format
  ```

- `format-check`: Check if code is formatted correctly
  ```bash
  uv run just format-check
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

### Commit Tasks (`commit.just`)
Tasks for managing commits:

- **`commit-bump`**: Bump the version of the package using Commitizen.
  ```bash
  uv run just commit-bump
  ```

- **`commit-files`**: Create a conventional commit using Commitizen.
  ```bash
  uv run just commit-files
  ```

- **`commit-info`**: Retrieve commit information using Commitizen.
  ```bash
  uv run just commit-info
  ```

- **`check-hooks`**: Run all pre-commit hooks to ensure code quality.
  ```bash
  uv run just check-hooks
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
- `check` runs all check tasks
