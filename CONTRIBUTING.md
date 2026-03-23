# Contributing to strands-compose

Thank you for your interest in contributing! Whether it's a bug report, new feature, correction, or additional documentation, we greatly value feedback and contributions from our community.

Please read through this document before submitting any issues or pull requests to ensure we have all the necessary information to effectively respond to your bug report or contribution.

## Reporting Bugs / Feature Requests

We welcome you to use [GitHub Issues](https://github.com/strands-compose/sdk-python/issues) to report bugs or suggest features.

When filing an issue, please check [existing issues](https://github.com/strands-compose/sdk-python/issues) first and try to include:

- A reproducible test case or series of steps
- The version of strands-compose being used
- Any modifications you've made relevant to the bug
- A minimal `config.yaml` that reproduces the issue

## Finding Contributions to Work On

Looking at existing issues is a great way to find something to contribute. Before starting work:

1. Check if someone is already assigned or working on it
2. Comment on the issue to express your interest
3. Wait for maintainer confirmation before beginning significant work

## Development Tenets

These principles guide every design decision in strands-compose. When contributing, please keep them in mind:

1. **Strands-first** — if strands provides it, use it; don't wrap unnecessarily
2. **Composition over inheritance** — small, focused components that compose
3. **Explicit over implicit** — no auto-registration, no global singletons
4. **Single responsibility** — each module does one thing
5. **Testable in isolation** — no global state, unit-testable without other components
6. **Thin wrapper** — translate YAML to Python objects, then get out of the way

## Development Environment

### Prerequisites

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) package manager
- Git

### Getting Started

```bash
git clone https://github.com/strands-compose/sdk-python
cd sdk-python
uv run just install
```

This installs all dependencies **and** wires the git hooks in one step.
If you only want to (re-)install the hooks later:

```bash
uv run just install-hooks
```

### Pre-commit Hooks

Three hook stages are registered automatically by `just install-hooks`:

| Stage | Triggered by | Runs |
|---|---|---|
| `pre-commit` | `git commit` | ruff lint + format, file checks, detect-secrets |
| `pre-push` | `git push` | same as above |
| `commit-msg` | `git commit` | commitizen validates conventional commit format |

> **Note:** `.git/hooks/` is not tracked by git. Every fresh clone requires running `uv run just install-hooks` once.

### Quality Checks

```bash
uv run just check    # format + lint + type check + security
uv run just test     # pytest with coverage (≥70%)
uv run just format   # auto-format with Ruff
```

### Coding Standards

All coding standards — type annotations, docstrings, naming, module organization, testing, and security rules — are documented in **[AGENTS.md](AGENTS.md)**. This is the single source of truth for how code should be written in this project.

## Contributing via Pull Requests

Contributions via pull requests are much appreciated. Before sending us a pull request, please ensure that:

1. You are working against the latest source on the `main` branch
2. You check existing open and recently merged pull requests to make sure someone else hasn't addressed the problem already
3. You open an issue to discuss any significant work — we would hate for your time to be wasted

To send us a pull request:

1. Create a branch from `main`
2. Make your changes — focus on the specific contribution
3. Run `uv run just check && uv run just test`
4. Commit using [Conventional Commits](https://www.conventionalcommits.org/) (`feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`)
5. Open a PR with a clear description of what and why
6. Pay attention to any automated CI failures and stay involved in the conversation

### PR Checklist

- [ ] All checks pass (`uv run just check`)
- [ ] Tests pass with adequate coverage (`uv run just test`)
- [ ] New public APIs have docstrings and tests
- [ ] No hardcoded secrets or credentials
- [ ] Changes are focused — one concern per PR

## Security Issue Notifications

If you discover a potential security issue in this project we ask that you notify us via [GitHub Security Advisories](https://github.com/strands-compose/sdk-python/security/advisories/new). Please do **not** create a public GitHub issue.

## Licensing

See the [LICENSE](LICENSE) file for our project's licensing. We will ask you to confirm the licensing of your contribution.
