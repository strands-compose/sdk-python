"""06_mcp — MCP: All Connection Modes in One Example.

Demonstrates all three MCP client connection modes in a single agent:
  - server:  local Python MCP server (managed lifecycle via mcp_servers)
  - url:     real external HTTP server (AWS Knowledge MCP, no API key needed)
  - command: stdio subprocess (shown in config comments)

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
    print("Tools: calc_add/multiply/percentage (local MCP) + aws_* (AWS Knowledge MCP).")
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
