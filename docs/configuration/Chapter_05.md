# Chapter 5: Tools — Giving Agents Superpowers

[← Back to Table of Contents](README.md) | [← Previous: YAML Anchors](Chapter_04.md)

---

The `tools` field on an agent is a list of spec strings that tell strands-compose where to find Python tool functions.

```yaml
agents:
  analyst:
    model: default
    tools:
      - ./tools.py                          # All @tool functions from this file
      - ./tools.py:count_words              # One specific function
      - ./utils/                            # All @tool functions from all .py files in dir
      - my_package.tools                    # All @tool functions from an installed module
      - my_package.tools:special_function   # One specific function from a module
      - strands_tools.http_request          # A tool from strands' built-in tools
    system_prompt: "You analyze text using your tools."
```

## Spec Formats

| Format | What It Loads |
|--------|---------------|
| `./file.py` | All `@tool`-decorated functions from the file |
| `./file.py:func_name` | One specific function (auto-wrapped with `@tool` if needed) |
| `./dir/` | All `@tool` functions from all `.py` files in directory (skips `_`-prefixed files) |
| `module.path` | All `@tool` functions from an installed Python module |
| `module.path:func_name` | One specific function from a module |

## Writing Tool Functions

Tool functions must be decorated with `@tool` from strands:

```python
# tools.py
from strands.tools.decorator import tool

@tool
def count_words(text: str) -> int:
    """Count the number of words in the given text."""
    return len(text.split())

@tool
def reverse_text(text: str) -> str:
    """Reverse the given text."""
    return text[::-1]
```

The decorator registers the function's name, docstring (used as the tool description for the LLM), and parameter schema (derived from type hints). Functions **without** `@tool` are silently ignored when scanning a file or module.

## Single Function Lookups and Auto-Wrapping

When you use the colon syntax to load a specific function (`./file.py:my_func`), strands-compose does something helpful: if the function isn't decorated with `@tool`, it auto-wraps it for you (and logs a warning). This is safe because the intent is unambiguous — you explicitly named the function:

```yaml
tools:
  - ./helpers.py:calculate_tax   # Works even without @tool decorator
```

You'll see a warning in the logs:

```
WARNING | tool=<calculate_tax> | not decorated with @tool, wrapping automatically
```

For file/module-wide scanning (without `:`), only `@tool`-decorated functions are picked up. This prevents accidentally exposing internal helper functions.

## Path Resolution

Filesystem paths are resolved **relative to the config file**, not the working directory. This is critical — it means your config works regardless of where you run the Python script from:

```
project/
├── config.yaml          # tools: [./tools/analysis.py]
├── tools/
│   └── analysis.py      # Resolved relative to config.yaml's directory
└── main.py              # Can be run from anywhere
```

Module-based specs (`module.path:func`) use the standard Python import system — the module must be importable.

## Directory Scanning

The directory spec (`./dir/`) recursively loads all `.py` files in the directory, skipping any file whose name starts with `_`:

```
tools/
├── _helpers.py     # Skipped (underscore prefix)
├── __init__.py     # Skipped (underscore prefix)
├── analysis.py     # Loaded — all @tool functions extracted
└── formatting.py   # Loaded — all @tool functions extracted
```

> **Tips & Tricks**
>
> - Organize tools in a directory when you have many of them. One file per domain: `tools/math.py`, `tools/text.py`, `tools/database.py`.
> - The `strands_tools` package has built-in tools like `http_request`, `file_read`, `shell` — use them with `strands_tools.http_request`.
> - Each agent gets its own copy of tools. Two agents referencing the same file get independent tool instances.
> - Tool function docstrings are sent to the LLM as the tool description. Write good docstrings — they directly affect how well the model uses your tools.
> - Type hints on tool parameters become the JSON schema the LLM sees. Use `str`, `int`, `float`, `bool`, `list[str]`, etc. The more specific your types, the better the LLM calls your tools.

---

[Next: Chapter 6 — Hooks →](Chapter_06.md)
