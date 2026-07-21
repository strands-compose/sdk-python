# Strands Compose — Documentation

**[YAML Configuration Guide](configuration/README.md)** — the complete reference, from your
first one-agent config to nested multi-orchestration systems with MCP servers, hooks,
plugins, session persistence, and streaming. Read it in order, or jump to a chapter:

| # | Chapter | What it covers |
|---|---------|----------------|
| 1 | [The Basics](configuration/Chapter_01.md) | Your first config |
| 2 | [Models](configuration/Chapter_02.md) | Choosing your LLM |
| 3 | [Variables](configuration/Chapter_03.md) | Environment-driven config |
| 4 | [YAML Anchors](configuration/Chapter_04.md) | DRY config blocks |
| 5 | [Tools](configuration/Chapter_05.md) | Giving agents capabilities |
| 6 | [Hooks](configuration/Chapter_06.md) | Lifecycle middleware |
| 7 | [Session Persistence](configuration/Chapter_07.md) | Memory that survives restarts |
| 8 | [Conversation Managers](configuration/Chapter_08.md) | Controlling context windows |
| 9 | [MCP](configuration/Chapter_09.md) | External tool servers |
| 10 | [Orchestrations](configuration/Chapter_10.md) | Multi-agent systems |
| 11 | [Graph Conditions](configuration/Chapter_11.md) | Dynamic routing |
| 12 | [Nested Orchestrations](configuration/Chapter_12.md) | Composing systems |
| 13 | [Multi-File Configs](configuration/Chapter_13.md) | Splitting and merging |
| 14 | [Agent Factories](configuration/Chapter_14.md) | Custom agent construction |
| 15 | [Event Streaming](configuration/Chapter_15.md) | Real-time observability |
| 16 | [Name Sanitization](configuration/Chapter_16.md) | How names are handled |
| 17 | [The Loading Pipeline](configuration/Chapter_17.md) | What happens under the hood |
| 18 | [Full Reference](configuration/Chapter_18.md) | Every field at a glance |
| 19 | [Plugins](configuration/Chapter_19.md) | Reusable agent behaviors |

**[Quick Recipes](configuration/Quick_Recipes.md)** — copy-paste-ready configs for common patterns.

## Learn by example

Every concept above has a runnable demo in **[examples/](../examples/)** — each a
self-contained folder with a `config.yaml`, a `main.py`, and its own README.

## What's in this folder

- `configuration/` — the YAML configuration guide (chapters plus quick recipes).
- `img/` — brand assets

---

Back to the [project README](../README.md).
