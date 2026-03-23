"""13_graph_conditions — Graph with Conditional Edges.

A write -> review -> publish pipeline where the reviewer can send content
back for revision or approve it for publication. Conditional edges
let an agent's output decide the next step.

Usage:
    uv run python examples/13_graph_conditions/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Write a short blog post about why YAML is great for configuration."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    graph = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("writer -> reviewer -> (writer again | publisher)")
    print("Type a message and press Enter. Empty line to exit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                break
            print("\nPipeline is running...")
            result = graph(msg)
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
