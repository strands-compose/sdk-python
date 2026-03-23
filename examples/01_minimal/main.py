"""01_minimal — Hello, Agent.

Load a single agent from config.yaml with load() and start an interactive REPL.

Usage:
    uv run python examples/01_minimal/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"


def main() -> None:
    """Load agent from config.yaml and run an interactive REPL."""
    from strands_compose import load

    # Load the agent config
    resolved = load(CONFIG)
    agent = resolved.entry

    # ── Run ────────────────────────────────────────────────────────────────────
    print(f"\n{52 * '-'}")
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
