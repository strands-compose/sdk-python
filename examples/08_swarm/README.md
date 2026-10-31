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

strands injects a `handoff_to_agent(agent_name, message, context)` tool into every swarm
agent. When an agent calls it, execution transfers to the named peer.

The next agent starts fresh. It sees the handoff `message`, the original request, the
names of the agents before it, and any `context` they shared. It does **not** see their
replies, and a revisited agent does not remember its own earlier turn. That is why every
prompt in `config.yaml` says to put the complete code in the handoff message.

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

**Pass the work in the handoff.** If an agent writes code in its reply but hands off
without it, the next agent has nothing to review. It ends up asking you to paste the code.

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

## Advanced topic — console output

Strands agents print their answer and tool calls through the default `callback_handler`.
This example's `main.py` prints nothing itself, so that output is all you see.
Set the handler to `null` in `agent_kwargs` to silence one agent:

```yaml
agents:
  my_agent:
    agent_kwargs:
      callback_handler: null # or ~
```

Only silence helper agents in a multi-agent setup. On the agent that gives the final
answer, you would see no answer at all.
