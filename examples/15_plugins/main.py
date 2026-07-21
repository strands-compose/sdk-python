"""15_plugins — Plugins.

Wires three vended plugins declared in config.yaml, each solving a real problem:

* ``strands:AgentSkills`` — loads the ``skills/`` directory (a Conventional Commits
  skill) so the agent pulls in full instructions on demand instead of carrying them
  in the prompt.
* ``ContextInjector`` (built by ``make_clock_injector`` in plugins.py) — folds the
  current UTC time into every model call without persisting it to history.
* ``GoalLoop`` — re-invokes the agent until its answer meets a quality bar.

Usage:
    uv run python examples/15_plugins/main.py
"""

from __future__ import annotations

import os
from pathlib import Path

HERE = Path(__file__).parent
CONFIG = HERE / "config.yaml"
STARTER = "Write a commit message for: added pagination to the /users endpoint."


def main() -> None:
    from strands_compose import load

    # AgentSkills reads `skills: ./skills` from plugin params, which strands-compose
    # forwards verbatim (params paths are not rewritten). Run from the config's
    # directory so ./skills resolves regardless of where this script is launched.
    os.chdir(HERE)

    resolved = load(CONFIG)
    agent = resolved.entry
    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("The agent has three plugins wired:")
    print("  - AgentSkills     (a Conventional Commits skill from skills/)")
    print("  - ContextInjector (live UTC time, built by a factory)")
    print("  - GoalLoop        (retries until the answer is concise)")
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
    finally:
        resolved.mcp_lifecycle.stop()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    from strands_compose import cli_errors

    with cli_errors():
        main()
