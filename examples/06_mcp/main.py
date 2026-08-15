"""06_mcp — MCP: Both Connection Modes in One Example.

Demonstrates both MCP client connection modes in a single agent:
  - command: stdio subprocess (local calculator_server.py)
  - url:     external HTTP server (AWS Knowledge MCP, no API key needed)

Usage:
    uv run python examples/06_mcp/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "What is 15% of 240? Also, what is Amazon S3?"


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("Tools: calc_add/multiply/percentage (stdio MCP) + aws_* (AWS Knowledge MCP).")
    print("Type a message and press Enter. Empty line to exit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                break
            print()
            agent(msg)
            print("\n" + 52 * "-" + "\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from strands_compose import cli_errors

    with cli_errors():
        main()
