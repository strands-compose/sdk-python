# Releasing strands-compose

Releases are driven by [Conventional Commits](https://www.conventionalcommits.org/) and automated via [commitizen](https://commitizen-tools.github.io/commitizen/) + GitHub Actions.

## Release Flow

```bash
# 1. Ensure main is green
uv run just check
uv run just test

# 2. Preview the bump (no changes written)
uv run just release-dry

# 3. Bump version, update CHANGELOG, create tag
uv run just release

# 4. Push to trigger PyPI publish
git push origin main --tags
```

That's it. The `publish.yml` workflow builds, publishes to PyPI via Trusted Publishing, and creates a GitHub Release automatically.

## How Versioning Works

We follow **Semantic Versioning** (`MAJOR.MINOR.PATCH`). Commit messages drive the bump:

| Commit prefix | Bump | Example |
|---------------|------|---------|
| `fix:` | patch | `fix: handle empty tool name` |
| `feat:` | minor | `feat: add graph orchestration` |
| `feat!:` / `BREAKING CHANGE:` | major | `feat!: remove legacy API` |

Use `uv run just commit-files` for the interactive commit wizard, or commit manually.

## Release Candidates

```bash
uv run cz bump --prerelease rc
git push origin main --tags
```

## Just Commands

| Command | What it does |
|---------|-------------|
| `uv run just release-dry` | Preview next version + changelog |
| `uv run just release` | Bump, CHANGELOG, tag |
| `uv run just release-build` | Build wheel + sdist locally |
| `uv run just commit-files` | Interactive conventional commit |
