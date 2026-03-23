"""02_vars_and_anchors — Variables & YAML Anchors for DRY configuration.

Demonstrates two YAML patterns for reducing duplication:
  1. Variables  — ${VAR:-default} for environment-driven, deployment-specific values
  2. Anchors    — &anchor / *alias for reusing YAML blocks without repetition

Try overriding at runtime:
  MODEL=us.anthropic.claude-sonnet-4-6-v1:0 uv run python examples/02_vars_and_anchors/main.py
  TONE=formal uv run python examples/02_vars_and_anchors/main.py
"""

from __future__ import annotations

import os
from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"


def main() -> None:
    from strands_compose import load, load_config

    # ── Show the resolved var and anchor values before running ───────────────
    config = load_config(CONFIG)
    print("\n[config.yaml — resolved variables & anchors]")
    print(f"  model      : {config.models['default'].model_id}")
    print(f"  tone       : {os.environ.get('TONE', 'friendly')}")
    print(f"  log_level  : {config.log_level}")
    # Anchors preserve types! max_tokens is an integer, not a string
    max_tokens = config.models["default"].params.get("max_tokens")
    if max_tokens:
        print(f"  max_tokens : {max_tokens} ({type(max_tokens).__name__})")

    # ── Run ────────────────────────────────────────────────────────────────────
    resolved = load(CONFIG)
    agent = resolved.entry
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
