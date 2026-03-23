"""10_nested — Nested Orchestration.

A Swarm (content_team) embedded inside a Delegate (pipeline).
strands-compose topological sort builds the inner swarm first, then wires
it as a delegate tool for the coordinator — all from config.yaml.

Usage:
    uv run python examples/10_nested/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Write a short, 5-sentence article about Python."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("coordinator -> [content_team(researcher <-> reviewer), qa_bot]")
    print("Type a message and press Enter. Empty line to exit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                break
            print("\nAgent is thinking...")
            result = agent(msg)
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
