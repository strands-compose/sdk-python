# Security Policy

## Supported Versions

| Version | Supported          |
|---------|--------------------|
| 0.1.x   | :white_check_mark: |

## Reporting Security Issues

We take security seriously. Please **do not** open a public GitHub issue for security vulnerabilities.

Instead, please report via [GitHub Security Advisories](https://github.com/strands-compose/sdk-python/security/advisories/new).

Include:
- Description of the vulnerability
- Steps to reproduce
- Potential impact
- Suggested fix (if any)

## Security Practices

strands-compose enforces the following (via Bandit + code review):

- **No `eval()` or `exec()`** — config is parsed through Pydantic, never executed as code
- **No `subprocess` with `shell=True`** — MCP stdio transports use direct command execution
- **No hardcoded secrets** — all credentials resolved from environment variables
- **No `pickle`** — serialization uses JSON/YAML only
- **Strict input validation** — all YAML config validated against a Pydantic schema
- **Bandit scanning** — automated static security analysis on every commit (`uv run just check-security`)
- **Dependency auditing** — dependencies are pinned and regularly reviewed for known vulnerabilities
