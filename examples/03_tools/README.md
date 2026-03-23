# 03 — Python Tools

> Give an agent Python functions as tools — YAML references your code directly.

## What this shows

The `tools:` key in an agent config lets you point at your Python code.
strands-compose loads it and registers matching functions with the agent.

## How it works

Add a `tools:` list to any agent definition. Each entry is a tool spec string — a path to
a file, a directory, or a Python module.

```yaml
agents:
  analyst:
    tools:
      - ./tools.py          # all @tool functions from a file
```

Supported tool spec formats:

| Format | What it loads |
|---|---|
| `./tools.py` | all `@tool`-decorated functions in the file |
| `./tools.py:count_words` | one specific function (decorator optional) |
| `./tools/` | all `.py` files in a directory (skips `_`-prefixed) |
| `my_module` | all `@tool` functions from an installed module |
| `my_module:my_func` | one specific function (decorator optional) |

## Good to know

**Decorate your tools with `@tool`.**
We recommend always using `@tool` from strands. The decorator tells strands-compose which
functions are tools and uses the docstring as the description the LLM sees.

When you load a whole file or directory, only `@tool`-decorated functions are picked up —
plain functions are silently skipped. This is handy: you can keep helpers in the same file
without worrying about them leaking as tools.

When you name a function explicitly with a colon (`./tools.py:my_func`), `@tool` is
optional — strands-compose will auto-wrap it for you (with a warning). But we still
recommend adding `@tool` for clarity and to make sure the docstring-based description
works as expected.

**Paths are relative to the config file**, not the working directory.

**Write clear docstrings** — the LLM uses them to decide when to call each tool.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/03_tools/main.py
```

## Try these prompts

- `Count the words and characters in: "The quick brown fox jumps over the lazy dog"`
- `How many sentences does this paragraph have? "Alice was beginning to get very tired. She had nothing to do. Suddenly a white rabbit ran by."`
- `Reverse the words in: "Hello world from strands-compose"`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
