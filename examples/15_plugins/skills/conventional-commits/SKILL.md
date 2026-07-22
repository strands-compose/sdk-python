---
name: conventional-commits
description: Write git commit messages that follow the Conventional Commits standard. Use when the user asks for a commit message, or gives a change summary or diff and wants it written up for git.
license: Apache-2.0
---

# Conventional Commits

Turn a description of a code change into a commit message that follows the
[Conventional Commits](https://www.conventionalcommits.org/) standard.

## When to use

Activate when the user asks for a commit message, or hands you a change summary
or diff and wants it phrased for git.

## Format

```
<type>(<optional scope>): <short summary>

<optional body>

<optional footer>
```

- **type** — one of `feat`, `fix`, `docs`, `refactor`, `test`, `perf`, `build`, `ci`, `chore`.
- **scope** — the area touched, e.g. `(api)`, `(auth)`. Optional.
- **summary** — imperative mood, lowercase, no trailing period, 72 characters or fewer.
- **body** — what changed and why, wrapped near 72 characters. Optional.
- **footer** — `BREAKING CHANGE: ...` and issue refs like `Closes #123`. Optional.

## Steps

1. Choose the single `type` that best fits the change. If it does more than one thing, suggest splitting the commit.
2. Add a `scope` only when it clarifies where the change lives.
3. Write the summary in the imperative ("add", not "added" or "adds").
4. Add a body only when the *why* is not obvious from the summary.
5. Record breaking changes in the footer with `BREAKING CHANGE:` and a short migration hint.

## Examples

Input: "added pagination to the users list endpoint"

```
feat(api): add pagination to the users list endpoint
```

Input: "fixed a crash when the config file is missing; now we fall back to defaults"

```
fix(config): fall back to defaults when the config file is missing

A missing config previously raised at startup. Loading now logs a warning
and uses the built-in defaults instead.
```

Input: "stopped reading the AWS_REGION env var; region now comes from config"

```
refactor(config): drop the AWS_REGION env var in favor of a region field

BREAKING CHANGE: AWS_REGION is no longer read. Set `region:` in your model
config instead.
```

## Edge cases

- Reverting a commit — use `revert: <original summary>` and put the reverted hash in the body.
- Several unrelated changes — recommend separate commits rather than one mega-commit.
- No obvious type — ask what the change is meant to accomplish before guessing.
