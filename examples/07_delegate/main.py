"""07_delegate — Multi-Agent Delegation.

A coordinator agent calls researcher and writer as tools.
strands-compose wires the connections from config.yaml automatically.

Usage:
    uv run python examples/07_delegate/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Write a short guide on how Python manages memory."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("coordinator -> researcher + writer")
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
