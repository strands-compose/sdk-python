# 15 — Plugins

> Extend an agent with reusable behaviour packages — skills, context injection, and quality loops.

## What plugins are for

A plugin changes how an agent behaves. Instead of cramming every instruction and
safeguard into one system prompt, you attach self-contained packages that hook into
the agent loop. The strands SDK ships several out of the box:

- **[Skills](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/)** — on-demand instructions the agent discovers and loads only when relevant, keeping the base prompt lean.
- **[Steering](https://strandsagents.com/docs/user-guide/concepts/plugins/steering/)** — just-in-time guidance and guardrails for long, multi-step tasks.
- **[Context Offloader](https://strandsagents.com/docs/user-guide/concepts/plugins/context-offloader/)** — moves oversized tool results to storage and hands the agent a preview plus a retrieval tool.
- **[Context Injector](https://strandsagents.com/docs/user-guide/concepts/plugins/context-injector/)** — folds real-time facts (a clock, environment data, a lookup) into each model call without persisting them.
- **[GoalLoop](https://strandsagents.com/docs/user-guide/concepts/plugins/goal-loop/)** — validates a response and retries with feedback until it meets a quality bar.

See the [strands plugins guide](https://strandsagents.com/docs/user-guide/concepts/plugins/)
for the full list and how to build your own.

## What this example wires

Three vended plugins, each solving a distinct problem:

```yaml
plugins:
  - type: strands:AgentSkills                 # on-demand skills from ./skills
    params:
      skills: ./skills

  - type: ./plugins.py:make_clock_injector    # live UTC time, via a factory

  - type: strands.vended_plugins.goal:GoalLoop # retry until the answer is concise
    params:
      goal: "Answer in at most three sentences, in plain language with no jargon."
      max_attempts: 2
```

Each entry is a `type:` import spec plus optional `params:`. Two forms of import spec work:

- `module.path:Name` — resolved from an installed package (`strands:AgentSkills`, `strands.vended_plugins.goal:GoalLoop`).
- `./file.py:Name` — resolved from a local file, relative to `config.yaml`.

## Class vs. factory

`GoalLoop` and `AgentSkills` take plain values, so they configure straight from `params`.
`ContextInjector` needs a *callable* to render the injected text, which a YAML scalar
can't express. `make_clock_injector` (in `plugins.py`) builds that callable and returns
the ready plugin. strands-compose calls the resolved object with `params` either way, so
a factory and a class look identical in the config. Reach for a factory whenever a plugin
needs a live argument — a callable, a storage backend, a set of providers.

## The skill

`skills/conventional-commits/SKILL.md` teaches the agent to write git commit messages
that follow the [Conventional Commits](https://www.conventionalcommits.org/) standard —
procedural knowledge that would bloat a system prompt but belongs in an on-demand skill.
It is a self-contained skill: YAML frontmatter (`name`, `description`, `license`) plus a
markdown body with format, steps, examples, and edge cases.

`AgentSkills` injects only the `name` and `description` into the system prompt at startup;
the full body loads when the agent activates the skill. Skills that ship resource files
(scripts, references, assets) also need a file-reading tool such as `file_read` from
[`strands-agents-tools`](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/#providing-tools-for-resource-access) —
this instruction-only skill needs none.

For the SKILL.md anatomy, the frontmatter fields, and the resource-directory layout,
see the authoring guide in [Chapter 19 — Plugins](../../docs/configuration/Chapter_19.md#authoring-a-skill-skillmd).
Agent Skills is an open, cross-vendor format — the authoritative sources are the
[strands skills docs](https://strandsagents.com/docs/user-guide/concepts/plugins/skills/)
and the [Agent Skills specification](https://agentskills.io/specification).

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/15_plugins/main.py
```

## Try these prompts

- `Write a commit message for: added pagination to the /users endpoint.` — the agent activates the Conventional Commits skill.
- `What time is it right now?` — answered from the injected UTC time.
- `Explain how strands plugins work.` — `GoalLoop` keeps the answer tight and filler-free.
