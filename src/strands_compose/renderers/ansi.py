"""Zero-dependency ANSI renderer for :class:`~strands_compose.wire.StreamEvent` objects.

Colour codes are automatically suppressed when stdout is not a TTY
(piped / redirected output).

Usage::

    from strands_compose import AnsiRenderer

    renderer = AnsiRenderer()
    while (event := await queue.get()) is not None:
        renderer.render(event)
    renderer.flush()

Key Features:
    - Automatic TTY detection with color suppression for piped output
    - Inline token and reasoning streaming with mode-change separators
    - Full event type coverage including multi-agent orchestration events
"""

from __future__ import annotations

import shutil
import sys
import time
from collections.abc import Callable
from typing import Any

from ..types import EventType
from ..wire import StreamEvent
from .base import EventRenderer


class AnsiRenderer(EventRenderer):
    """Renders events using raw ANSI escape codes."""

    def __init__(
        self,
        *,
        file: Any | None = None,
        separator_width: int | None = None,
        typewriter_delay: float = 0.0,
    ) -> None:
        """Initialize the AnsiRenderer.

        No third-party dependencies.  Colour codes are automatically
        suppressed when stdout is not a TTY (piped / redirected output).

        Token and reasoning events are written inline (no trailing newline)
        so they appear as a continuous stream.  A separator line is printed
        when the mode changes between reasoning and responding, or when the
        active agent changes.

        Args:
            file: Output stream (defaults to ``sys.stdout``).
            separator_width: Width of separator lines. Defaults to 70 or the
                current terminal width, whichever is available.
            typewriter_delay: Seconds to sleep after each printable character
                in TOKEN and REASONING events.  ``0.0`` (default) disables
                the effect entirely with no overhead.
        """
        self._out = file or sys.stdout
        self._in_stream = False
        self._mode: str | None = None  # "reasoning" | "responding" | None
        self._active_agent: str | None = None
        self._typewriter_delay = typewriter_delay

        # Cache TTY state and pre-compute ANSI escape strings.
        is_tty = hasattr(self._out, "isatty") and self._out.isatty()
        self._dim = "\033[2m" if is_tty else ""
        self._bold = "\033[1m" if is_tty else ""
        self._cyan = "\033[36m" if is_tty else ""
        self._green = "\033[32m" if is_tty else ""
        self._red = "\033[31m" if is_tty else ""
        self._yellow = "\033[33m" if is_tty else ""
        self._magenta = "\033[95m" if is_tty else ""
        self._reset = "\033[0m" if is_tty else ""

        if separator_width is not None:
            self._separator_width = separator_width
        else:
            self._separator_width = shutil.get_terminal_size((70, 24)).columns

        self._handlers: dict[str, Callable[[StreamEvent], None]] = {
            EventType.TOKEN: self._handle_token,
            EventType.AGENT_START: self._handle_agent_start,
            EventType.TOOL_START: self._handle_tool_start,
            EventType.TOOL_END: self._handle_tool_end,
            EventType.COMPLETE: self._handle_complete,
            EventType.ERROR: self._handle_error,
            EventType.NODE_START: self._handle_node_start,
            EventType.NODE_STOP: self._handle_node_stop,
            EventType.HANDOFF: self._handle_handoff,
            EventType.MULTIAGENT_START: self._handle_multiagent_start,
            EventType.MULTIAGENT_COMPLETE: self._handle_multiagent_complete,
            EventType.REASONING: self._handle_reasoning,
        }

    # -- Public API --------------------------------------------------------

    def render(self, event: StreamEvent) -> None:  # noqa: D102
        handler = self._handlers.get(event.type)
        if handler is not None:
            handler(event)

    def flush(self) -> None:  # noqa: D102
        if self._in_stream:
            self._out.write("\n")
            self._out.flush()
            self._in_stream = False

    # -- Per-event-type handlers -------------------------------------------

    def _handle_token(self, event: StreamEvent) -> None:
        self._ensure_mode(event.agent_name, "responding")
        text = event.data.get("text", "")
        self._write_with_delay(text)
        self._in_stream = True

    def _handle_reasoning(self, event: StreamEvent) -> None:
        self._ensure_mode(event.agent_name, "reasoning")
        text = event.data.get("text", "")
        self._out.write(self._yellow)
        self._write_with_delay(text)
        self._out.write(self._reset)
        self._out.flush()
        self._in_stream = True

    def _handle_agent_start(self, event: StreamEvent) -> None:
        self._break()
        self._mode = None
        self._active_agent = None
        self._out.write(self._separator(event.agent_name, "AGENT START", color=self._magenta))
        self._out.write(f"{self._cyan}{self._bold}[{event.agent_name}]{self._reset} starting…\n")
        self._out.flush()

    def _handle_tool_start(self, event: StreamEvent) -> None:
        self._break()
        self._mode = None
        self._active_agent = None
        data = event.data
        label = data.get("tool_label") or data.get("tool_name", "unknown")
        tool_input = data.get("tool_input", {})
        preview = str(tool_input)[:80] + ("…" if len(str(tool_input)) > 80 else "")
        self._out.write(self._separator(event.agent_name, "TOOL USE", color=self._magenta))
        self._out.write(
            f"  {self._yellow}⚙{self._reset}  [{event.agent_name}] -> {label!r}"
            f"  {self._dim}{preview}{self._reset}\n"
        )
        self._out.flush()

    def _handle_tool_end(self, event: StreamEvent) -> None:
        self._break()
        self._mode = None
        status = event.data.get("status", "?")
        agent = event.agent_name
        if status == "error":
            self._out.write(
                f"  {self._red}✗{self._reset}  [{agent}] tool error: {event.data.get('error')}\n"
            )
        else:
            self._out.write(f"  {self._green}✓{self._reset}  [{agent}] tool done\n")
        self._out.flush()

    def _handle_complete(self, event: StreamEvent) -> None:
        self._break()
        self._mode = None
        self._active_agent = None
        usage = event.data.get("usage", {})
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
        self._out.write(
            f"  {self._dim}✅  [{event.agent_name}] complete  ({in_tokens} input, {out_tokens} output tokens){self._reset}\n"
        )
        self._out.flush()

    def _handle_error(self, event: StreamEvent) -> None:
        self._break()
        self._mode = None
        self._out.write(self._separator(event.agent_name, "ERROR", color=self._red))
        msg = event.data.get("message", "unknown error")
        exc_type = event.data.get("exception_type")
        if exc_type and msg.startswith(f"{exc_type}: "):
            detail = msg[len(exc_type) + 2 :]
            self._out.write(
                f"  {self._red}✗  [{event.agent_name}] ERROR: {exc_type}:\n"
                f"     {detail}{self._reset}\n"
            )
        else:
            self._out.write(f"  {self._red}✗  [{event.agent_name}] ERROR: {msg}{self._reset}\n")
        self._out.flush()

    def _handle_node_start(self, event: StreamEvent) -> None:
        self._break()
        self._out.write(
            f"\n{self._cyan}->{self._reset}  node '{event.data.get('node_id')}'  starting\n"
        )
        self._out.flush()

    def _handle_node_stop(self, event: StreamEvent) -> None:
        self._break()
        self._out.write(f"{self._cyan}←{self._reset}  node '{event.data.get('node_id')}'  done\n")
        self._out.flush()

    def _handle_handoff(self, event: StreamEvent) -> None:
        self._break()
        to_ids = ", ".join(event.data.get("to_node_ids", []))
        self._out.write(f"  {self._cyan}↪{self._reset}  handoff -> {to_ids}\n")
        self._out.flush()

    def _handle_multiagent_start(self, event: StreamEvent) -> None:
        self._break()
        kind = event.data.get("multiagent_type", "")
        self._out.write(f"\n{self._cyan}⊕{self._reset}  {kind} orchestration starting\n")
        self._out.flush()

    def _handle_multiagent_complete(self, event: StreamEvent) -> None:
        self._break()
        kind = event.data.get("multiagent_type", "")
        self._out.write(f"{self._cyan}⊗{self._reset}  {kind} orchestration complete\n\n")
        self._out.flush()

    # -- Internal helpers --------------------------------------------------

    def _write_with_delay(self, text: str) -> None:
        """Write *text* to the output stream, sleeping between printable characters.

        When :attr:`_typewriter_delay` is ``0.0`` the text is written in a
        single call with no per-character overhead.  Otherwise each printable
        character is written individually, flushed, and followed by a
        ``time.sleep`` call so that the typewriter effect is visible.
        Whitespace and control characters are written without a delay to
        avoid stutter on word boundaries.
        """
        if self._typewriter_delay <= 0.0:
            self._out.write(text)
            self._out.flush()
            return
        for char in text:
            self._out.write(char)
            self._out.flush()
            if char.isprintable() and not char.isspace():
                time.sleep(self._typewriter_delay)

    def _break(self) -> None:
        """Insert a newline if we are mid-token/reasoning stream."""
        if self._in_stream:
            self._out.write("\n")
            self._out.flush()
            self._in_stream = False

    def _separator(self, agent: str, label: str, color: str | None = None) -> str:
        """Build a separator line like ``── agent — REASONING ──``."""
        c = color if color is not None else self._dim
        inner = f" {agent} \u2014 {label} "
        pad = max(0, self._separator_width - len(inner) - 4)
        left = 2
        right = pad - left if pad > left else 0
        return f"\n{c}{'─' * left}{inner}{'─' * right}{self._reset}\n"

    def _ensure_mode(self, agent: str, mode: str) -> None:
        """Print a separator when the agent or mode changes."""
        if mode == self._mode and agent == self._active_agent:
            return
        self._break()
        self._active_agent = agent
        self._mode = mode
        label = "REASONING" if mode == "reasoning" else "RESPONDING"
        color = self._yellow if mode == "reasoning" else self._cyan
        self._out.write(self._separator(agent, label, color=color))
        self._out.flush()
