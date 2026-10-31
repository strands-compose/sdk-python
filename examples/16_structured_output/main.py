"""16_structured_output — Typed Agent Results.

The triage agent returns a ``Ticket`` (see schemas.py) for every message.
The REPL prints that typed object instead of free text.

Usage:
    uv run python examples/16_structured_output/main.py
"""

from __future__ import annotations

from pathlib import Path

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "I was charged twice for my subscription this month and nobody has replied."


def main() -> None:
    """Load the triage agent and print the Ticket it returns for each message."""
    from strands_compose import load

    resolved = load(CONFIG)
    agent = resolved.agents["triage"]

    # ── Run ────────────────────────────────────────────────────────────────────
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("Type a support message and press Enter. Empty line to exit.\n")
    try:
        while True:
            msg = input("You: ").strip()
            if not msg:
                break
            result = agent(msg)
            # A Ticket instance, not text: read its fields directly.
            print(f"\n{result.structured_output!r}")
            print("\n" + 52 * "-" + "\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from strands_compose import cli_errors

    with cli_errors():
        main()
