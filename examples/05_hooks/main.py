"""05_hooks — Hooks.

Demonstrates a custom FingerprintHook, MaxToolCallsGuard, and ToolNameSanitizer
(strips model-injected artifacts from tool names), all declared inline in config.yaml.

Usage:
    uv run python examples/05_hooks/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Research the impact of electric vehicles on city air quality. Be thorough."


def main() -> None:
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print(
        "Watch for the CUSTOM HOOK summary line after each response — that's FingerprintHook counting tool calls."
    )
    print("MaxToolCallsGuard will stop the agent after 5 tool calls.")
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
