"""08_swarm — Autonomous Handoffs.

Peer agents hand work off to each other via handoff_to_agent.
strands-compose builds the Swarm from config.yaml automatically.

Usage:
    uv run python examples/08_swarm/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Write and review a Python function that validates an email address."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    swarm = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("drafter -> reviewer -> tech_lead (autonomous handoffs)")
    print("Type a message and press Enter. Empty line to exit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                break
            print("\nSwarm is working...")
            result = swarm(msg)
            print(f"\n\n{52 * '-'}")
            print(f"Agent: {result}\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        resolved.mcp_lifecycle.stop()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from strands_compose import cli_errors

    with cli_errors():
        main()
