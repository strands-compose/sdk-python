"""04_session — Persistent Memory.

Declare a session_manager in config.yaml — strands-compose wires persistent
conversation history automatically. State is saved to .sessions/ on disk.

Usage:
    uv run python examples/04_session/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "My name is Alice and I work as a data engineer."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("The agent remembers everything you say — even across restarts.")
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
