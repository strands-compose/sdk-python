"""09_graph — Graph Pipeline.

A deterministic DAG: content_strategist -> content_writer -> copy_editor.
strands-compose builds the graph from edges defined in config.yaml.

Usage:
    uv run python examples/09_graph/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Write a blog post about why Rust is gaining popularity among Python developers."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    graph = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("content_strategist -> content_writer -> copy_editor (fixed order)")
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
