# 08 — Swarm (Autonomous Handoffs)

> Peer agents that hand work off to each other — no central coordinator.

## What this shows

- `mode: swarm` in `orchestrations:` — agents decide on their own when to pass the baton
- `agents:` list — all participating peers
- `entry_name:` — which agent receives the initial task
- `max_handoffs:` — safety cap on total agent-to-agent transfers
- `handoff_to_agent` — a tool strands injects into every swarm agent automatically

## How it works

Unlike delegation (one boss calls sub-agents), a swarm has no fixed director.
Each agent decides autonomously when to hand off to a peer:

```
drafter ──handoff──▶ reviewer ──handoff──▶ drafter  (if revisions needed)
                                  └──handoff──▶ tech_lead  (when approved)
```

strands injects a `handoff_to_agent(agent_name, context)` tool into every swarm agent.
When an agent calls it, execution transfers to the named peer with full context.

```yaml
orchestrations:
  review_team:
    mode: swarm
    agents: [drafter, reviewer, tech_lead]
    entry_name: drafter
    max_handoffs: 10
```

## Good to know

**Swarm vs Delegate.** Use swarm when agents need to collaborate back-and-forth (e.g.
drafting + reviewing cycles). Use delegate when there's a clear hierarchy and fixed
flow.

**`max_handoffs` prevents infinite loops.** If agents keep handing off without
converging, the swarm stops after `max_handoffs` transfers.

**Swarm agents can't have a session manager.** If you have a global `session_manager:`,
any agent used in a swarm must opt out with `session_manager: ~`. This is a strands
limitation — may be lifted in the future.

## Prerequisites

- AWS credentials configured (`aws configure` or environment variables)
- Dependencies installed: `uv sync`

## Run

```bash
uv run python examples/08_swarm/main.py
```

## Try these prompts

- `Write and review a Python function that validates an email address.`
- `Create and review a function that merges two sorted lists.`
- `Write a utility that parses a simple key=value config file.`

## Advanced topic — suppress default callback logging

Strands agents log actions to the console through their default `callback_handler`.
If you want cleaner example output, set the handler to `null` in `agent_kwargs` for any agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```
