"""Tool-name sanitization hook.

Some models inject extra tokens into tool names (e.g. ``query<|channel|>commentary``
instead of ``query``). Strands cannot look up the original tool when that happens,
so the call silently fails. This hook strips the artifacts before Strands does its lookup.

Two-layer approach:

1. **AfterModelCallEvent** — rewrites names in the response *before*
   Strands does tool lookup.
2. **BeforeToolCallEvent** — safety net: cancels unresolvable garbled names
   with a descriptive error message fed back to the LLM.
"""

from __future__ import annotations

import logging
import re
import sys
from typing import TYPE_CHECKING, Any

from strands.hooks import HookProvider, HookRegistry
from strands.hooks.events import AfterModelCallEvent, BeforeToolCallEvent

if sys.version_info >= (3, 12):
    from typing import override
else:
    from typing_extensions import override

if TYPE_CHECKING:
    from strands.agent import Agent

logger = logging.getLogger(__name__)

# Matches artifact tokens injected by some models (e.g. <|channel|>).
# Used for both detection (.search) and splitting (.split).
_GARBAGE_RE = re.compile(r"[<|>]+")


def _find_best_prefix(name: str, allowed: set[str]) -> str | None:
    """Return the longest tool name in *allowed* that is a prefix of *name*."""
    best: str | None = None
    for tool in allowed:
        if name.startswith(tool) and (best is None or len(tool) > len(best)):
            best = tool
    return best


def _sanitize(raw: str, allowed: set[str]) -> str | None:
    """Try to recover a valid tool name from a garbled one.

    Strategy:
    1. Exact match -> return as-is.
    2. Prefix match on the raw garbled string (handles ``tool<|garbage``).
    3. Split on garbage chars, rejoin with ``_`` / ``-`` / nothing,
       try exact then prefix (handles ``a<|b|>c`` -> ``a_b_c``).

    Returns the corrected name, or ``None`` if no match found.
    """
    if raw in allowed:
        return raw

    if not _GARBAGE_RE.search(raw):
        return None

    best = _find_best_prefix(raw, allowed)
    if best:
        return best

    # Treat garbage runs as separators and try common join characters.
    # e.g. "reporter<|channel|>commentary" -> ["reporter","channel","commentary"]
    #       -> "reporter_channel_commentary" / "reporter-channel-commentary" / "reporterchannelcommentary"
    segments = [s for s in _GARBAGE_RE.split(raw) if s]
    for sep in ("_", "-", ""):
        candidate = sep.join(segments)[:64]
        if candidate in allowed:
            return candidate
        best = _find_best_prefix(candidate, allowed)
        if best:
            return best

    return None


class ToolNameSanitizer(HookProvider):
    """Strips model-injected artifacts from tool names so Strands can look them up.

    Registers on:
    - AfterModelCallEvent: rewrites tool names in the model response message.
    - BeforeToolCallEvent: safety net — fixes or cancels still-garbled names.
    """

    @override
    def register_hooks(self, registry: HookRegistry, **kwargs: Any) -> None:
        """Register AfterModelCall and BeforeToolCall sanitization callbacks."""
        registry.add_callback(AfterModelCallEvent, self._on_after_model)
        registry.add_callback(BeforeToolCallEvent, self._on_before_tool)

    @staticmethod
    def _known(agent: Agent) -> set[str]:
        """Return tool names from the agent's registry."""
        try:
            return set(agent.tool_registry.registry.keys())
        except Exception:
            logger.debug(
                "agent=<%s> | failed to read tool registry",
                getattr(agent, "name", "?"),
                exc_info=True,
            )
            return set()

    # -- Layer 1: fix names in the model response before tool lookup ----------

    def _on_after_model(self, event: AfterModelCallEvent) -> None:
        """Fix garbled tool names in the model's response message."""
        if event.stop_response is None:
            return

        content = event.stop_response.message.get("content", [])
        if not content:
            return

        known = self._known(event.agent)
        if not known:
            return

        for block in content:
            if not isinstance(block, dict) or "toolUse" not in block:
                continue

            tool_use = block["toolUse"]
            raw: str = tool_use.get("name", "")

            if raw in known:
                continue
            if not _GARBAGE_RE.search(raw):
                continue  # clean unknown name — not a garbling issue

            fixed = _sanitize(raw, known)
            if fixed:
                logger.info(
                    "original=<%s>, fixed=<%s> | sanitized tool name in model response", raw, fixed
                )
                tool_use["name"] = fixed
            else:
                # Leave garbled name intact so BeforeToolCall can cancel it
                # with a descriptive error (listing available tools).
                logger.warning(
                    "name=<%s> | cannot resolve garbled tool name in model response", raw
                )

    # -- Layer 2: safety net before tool execution ----------------------------

    def _on_before_tool(self, event: BeforeToolCallEvent) -> None:
        """Safety net — fix or cancel tool calls with garbled names."""
        raw: str = event.tool_use.get("name", "")
        known = self._known(event.agent)

        if raw in known:
            return
        if not _GARBAGE_RE.search(raw):
            return  # clean name, not our problem — let Strands handle it

        fixed = _sanitize(raw, known)
        if fixed:
            logger.info(
                "original=<%s>, fixed=<%s> | sanitized tool name before tool call", raw, fixed
            )
            event.tool_use["name"] = fixed
            try:
                tool = event.agent.tool_registry.registry.get(fixed)
                if tool:
                    event.selected_tool = tool
            except Exception:  # nosec B110
                logger.debug(
                    "tool=<%s> | failed to look up fixed tool in registry", fixed, exc_info=True
                )
            return

        event.cancel_tool = (
            f"Invalid tool name '{raw}'. "
            f"Available tools: {', '.join(sorted(known))}. "
            f"Please use an exact tool name from the list above."
        )
