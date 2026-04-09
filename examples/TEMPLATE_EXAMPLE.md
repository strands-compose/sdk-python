> Example README Template
>
> Use this structure for every example README in this directory.
> Keep the tone casual and user-friendly — explain what the example does and
> how to run it, but don't dive into internals unless relevant.
>
> Copy the skeleton below and fill in the sections.

---

# NN — Title

> One-line summary: what does this example show?

## What this shows

A short description (2–5 sentences or a bulleted list) of the features or
concepts this example covers. Focus on *what the user learns*, not on
implementation details.

## How it works

Explain the outer interface: which strands-compose functions or config keys
are used and what they produce. Keep it high-level — show a snippet or a
small diagram if helpful, but don't go deep into source code.

## Good to know

Optional section. Add tips, gotchas, or recommendations that help the user
at this stage. Remove this section if there's nothing extra to mention.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/NN_name/main.py
```

If there are environment variable overrides or platform differences, show them:

```bash
# Linux / macOS
VAR=value uv run python examples/NN_name/main.py

# Windows PowerShell
$env:VAR="value"; uv run python examples/NN_name/main.py
```

## Try these prompts

- `Prompt suggestion 1`
- `Prompt suggestion 2`
- `Prompt suggestion 3`
