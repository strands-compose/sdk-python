# ---------------------------------------------------------------------------
# Release tasks
#
# Normal release flow:
#   1. uv run just release-dry      -> preview version bump + changelog diff
#   2. uv run just release          -> bump version, update CHANGELOG, create tag
#   3. git push origin main --tags  -> triggers publish.yml CI/CD
# ---------------------------------------------------------------------------

# Preview the next version bump (no changes written)
[group('release')]
release-dry:
    uv run cz bump --dry-run

# Bump version, update CHANGELOG, and create a git tag
[group('release')]
release: check test
    uv run cz bump
    @echo ""
    @echo "✅  Version bumped. Push with:"
    @echo "      git push origin main --tags"

# Build distribution artifacts (local check)
[group('release')]
release-build:
    rm -rf dist/
    uv build --out-dir dist/
    @echo ""
    @ls dist/

# Publish to TestPyPI (safe dry-run against the test registry)
[group('release')]
release-test-publish:
    uv run python -m twine upload --repository testpypi dist/*

# Show the next version that commitizen would pick
[group('release')]
release-next:
    uv run cz bump --dry-run 2>&1 | grep -E "tag to create|bump" || echo "(no releasable commits since last tag)"
