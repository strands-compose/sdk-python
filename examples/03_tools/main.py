"""03_tools — Python Tools.

Load ``@tool``-decorated functions from an external file via tools: [./tools.py]
in config.yaml.  strands-compose discovers every ``@tool``-decorated function
and registers it with the Agent automatically.  Plain functions without the
decorator are ignored.

Usage:
    uv run python examples/03_tools/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = 'Count words and characters in: "The quick brown fox jumps over the lazy dog"'


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
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
