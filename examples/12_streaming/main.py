"""12_streaming — Streaming Agent Output.

Watch every token, tool call, and lifecycle event in real time.
wire_event_queue() wires all agents and returns an async queue.
AnsiRenderer prints each event with colours as it arrives.

Usage:
    uv run python examples/12_streaming/main.py
"""

from __future__ import annotations

import asyncio
from pathlib import Path

from strands_compose import AnsiRenderer, cli_errors, load

CONFIG = Path(__file__).parent / "config.yaml"
STARTER = "Analyse the impact of large language models on software engineering."


async def _stream(prompt: str, entry, queue):
    """Invoke the entry agent and render the event stream."""
    queue.flush()
    result = None

    async def _invoke() -> None:
        nonlocal result
        try:
            result = await entry.invoke_async(prompt)
        except Exception:
            pass  # nosec B110
        finally:
            await queue.close()

    asyncio.create_task(_invoke())

    renderer = AnsiRenderer()
    while (event := await queue.get()) is not None:
        renderer.render(event)
    renderer.flush()
    return result


async def _main() -> None:
    resolved = load(CONFIG)
    entry = resolved.entry
    queue = resolved.wire_event_queue()

    print(f"\n{52 * '-'}")
    print(f"Try: {STARTER}\n")
    print("researcher -> analyst -> coordinator (with live streaming)")
    print("Type a message and press Enter. Empty line to exit.\n")

    try:
        while True:
            msg = await asyncio.to_thread(lambda: input("You: ").strip())
            if not msg:
                break
            print("\nAgent is thinking...")
            result = await _stream(msg, entry, queue)
            print(f"\n\n{52 * '-'}")
            print(f"Agent: {result}\n")
    except KeyboardInterrupt:
        print("\nGoodbye!")
    finally:
        resolved.mcp_lifecycle.stop()


# ── entry point ───────────────────────────────────────────────────────────────

if __name__ == "__main__":
    with cli_errors():
        asyncio.run(_main())
