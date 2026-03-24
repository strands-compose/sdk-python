# Support

## Getting Help

- **[README](README.md)** — overview and quick start
- **[AGENTS.md](AGENTS.md)** — coding standards, architecture principles, and strands API reference
- **[Examples](examples/)** — working examples with Python + YAML

## Reporting Issues

If you encounter a bug or have a feature request:

1. Search [existing issues](https://github.com/strands-compose/sdk-python/issues) to avoid duplicates
2. Open a new issue with:
   - Clear title describing the problem
   - Steps to reproduce (for bugs)
   - Minimal `config.yaml` that reproduces the issue
   - Python version and strands-compose version

## Security

If you discover a potential security issue, please see [SECURITY.md](SECURITY.md).

## Troubleshooting

- If you see tool name errors, ensure the sanitizer is included in your hooks list

**Import errors:**
- Install optional dependencies: `pip install strands-compose[ollama]` for Ollama, `pip install strands-compose[openai]` for OpenAI
- Ensure Python 3.11+ is being used

## Strands Agents SDK

strands-compose is built on top of the [Strands Agents SDK](https://github.com/strands-agents/sdk-python). For questions about the underlying agent framework, model providers, or hook system, refer to the Strands documentation.
