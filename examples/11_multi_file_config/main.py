"""11_multi_file_config — Multi-File Config.

Split a single logical config across multiple YAML files.
Neither file is valid alone — together they form a complete config.

  base.yaml   — vars, models (infrastructure)
  agents.yaml — agents, entry (application)

Usage:
    uv run python examples/11_multi_file_config/main.py
    MODEL=us.anthropic.claude-sonnet-4-6-v1:0 uv run python examples/11_multi_file_config/main.py
"""

from __future__ import annotations

from pathlib import Path

BASE = Path(__file__).parent / "base.yaml"
AGENTS = Path(__file__).parent / "agents.yaml"


def main() -> None:
    from strands_compose import load

    resolved = load([BASE, AGENTS])
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print("Loaded: base.yaml + agents.yaml (merged)")
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
