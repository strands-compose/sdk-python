"""Zero-dependency ANSI renderer for StreamEvent objects.

Colour codes are automatically suppressed when stdout is not a TTY
(piped / redirected output).

Usage::

    from strands_compose import AnsiRenderer

    renderer = AnsiRenderer()
    while (event := await queue.get()) is not None:
        renderer.render(event)
    renderer.flush()
"""

from __future__ import annotations

import shutil
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..types import EventType, SessionManifest, StreamEvent
from .base import EventRenderer


@dataclass
class _Branch:
    """Render state for one agent's output.

    strands runs the tool calls of a single turn concurrently, so agents
    delegated in the same turn interleave their events.  Per-agent state keeps
    a neighbour's tokens from splitting an agent's block.

    Attributes:
        mode: Open stream mode (``"reasoning"``, ``"responding"``, or ``None``
            when the next chunk needs a fresh header).
        in_stream: Whether output is mid-line in a token/reasoning stream.
        ended: Whether the agent emitted its terminal event, so its buffered
            block is complete.
        pending_tools: Number of the agent's tool calls still running.
        buffer: Rendered output held back while another agent is live.
    """

    mode: str | None = None
    in_stream: bool = False
    ended: bool = False
    pending_tools: int = 0
    buffer: list[str] = field(default_factory=list)


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
        when an agent's mode changes between reasoning and responding.

        Concurrent agents are serialised rather than interleaved: one agent
        holds the terminal and streams live while the others' output is
        buffered, then written as a contiguous block once the live agent
        yields.  Each agent keeps a single header and an unbroken block, at
        the cost of that block appearing later than it was produced.

        Args:
            file: Output stream (defaults to ``sys.stdout``).
            separator_width: Width of separator lines. Defaults to 70 or the
                current terminal width, whichever is available.
            typewriter_delay: Seconds to sleep after each printable character
                in TOKEN and REASONING events.  ``0.0`` (default) disables
                the effect entirely with no overhead.
        """
        self._out = file or sys.stdout
        self._typewriter_delay = typewriter_delay

        # Insertion order decides the order buffered blocks are written in.
        self._branches: dict[str, _Branch] = {}
        self._owner: str | None = None

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
            EventType.SESSION_START: self._handle_session_start,
            EventType.SESSION_END: self._handle_session_end,
            EventType.TOKEN: self._handle_token,
            EventType.AGENT_START: self._handle_agent_start,
            EventType.TOOL_START: self._handle_tool_start,
            EventType.TOOL_END: self._handle_tool_end,
            EventType.AGENT_COMPLETE: self._handle_agent_complete,
            EventType.INTERRUPT: self._handle_interrupt,
            EventType.ERROR: self._handle_error,
            EventType.NODE_START: self._handle_node_start,
            EventType.NODE_STOP: self._handle_node_stop,
            EventType.HANDOFF: self._handle_handoff,
            EventType.MULTIAGENT_START: self._handle_multiagent_start,
            EventType.MULTIAGENT_COMPLETE: self._handle_multiagent_complete,
            EventType.REASONING: self._handle_reasoning,
        }

    # -- Public API --------------------------------------------------------

    def render(self, event: StreamEvent) -> None:
        handler = self._handlers.get(event.type)
        if handler is not None:
            handler(event)

    def flush(self) -> None:
        """Close the live stream, write every buffered block, and reset state.

        An agent that never emitted a terminal event still has output to write,
        so all remaining buffers are drained here.  State is cleared because a
        renderer is reused across turns.
        """
        if self._owner is not None:
            self._break(self._owner)
        for agent, branch in self._branches.items():
            self._write_buffer(agent)
            if branch.in_stream:
                self._out.write("\n")
        self._out.flush()
        self._branches.clear()
        self._owner = None

    # -- Per-event-type handlers -------------------------------------------

    def _handle_session_start(self, event: StreamEvent) -> None:
        manifest = SessionManifest.model_validate(event.data["manifest"])
        agent_names = ", ".join(a.name for a in manifest.agents) or "—"
        orch_names = ", ".join(o.name for o in manifest.orchestrations) or "—"
        text = (
            self._separator(manifest.entry.name, "SESSION START", color=self._cyan)
            + f"  {self._dim}entry:          {manifest.entry.name} ({manifest.entry.kind})\n"
            + f"  agents:         {agent_names}\n"
        )
        if manifest.orchestrations:
            text += f"  orchestrations: {orch_names}\n"
        self._write_direct(text + self._reset)

    def _handle_session_end(self, event: StreamEvent) -> None:
        session_id = event.data.get("session_id")
        sid_str = session_id if session_id else "—"
        self._write_direct(
            self._separator(event.agent_name, "SESSION END", color=self._cyan)
            + f"  {self._dim}session_id: {sid_str}{self._reset}\n"
        )

    def _handle_token(self, event: StreamEvent) -> None:
        text = event.data.get("text", "")
        branch = self._claim(event.agent_name)
        if branch.mode != "responding" and not text.strip():
            return
        self._ensure_mode(event.agent_name, "responding")
        self._emit(event.agent_name, text, stream=True)
        branch.in_stream = True

    def _handle_reasoning(self, event: StreamEvent) -> None:
        text = event.data.get("text", "")
        branch = self._claim(event.agent_name)
        if branch.mode != "reasoning" and not text.strip():
            return
        self._ensure_mode(event.agent_name, "reasoning")
        self._emit(event.agent_name, self._yellow)
        self._emit(event.agent_name, text, stream=True)
        self._emit(event.agent_name, self._reset)
        branch.in_stream = True

    def _handle_agent_start(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        self._emit(
            agent,
            self._separator(agent, "AGENT START", color=self._magenta)
            + f"{self._cyan}{self._bold}[{agent}]{self._reset} starting…\n",
        )

    def _handle_tool_start(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        label = event.data.get("tool_name", "unknown")
        tool_input = str(event.data.get("tool_input", {}))
        preview = tool_input[:80] + ("…" if len(tool_input) > 80 else "")
        self._emit(
            agent,
            self._separator(agent, "TOOL USE", color=self._magenta)
            + f"  {self._yellow}⚙{self._reset}  [{agent}] -> {label!r}"
            f"  {self._dim}{preview}{self._reset}\n",
        )
        # The agent is blocked on the tool, so the sub-agent it called runs next.
        self._branches[agent].pending_tools += 1
        self._release(agent)

    def _handle_tool_end(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        branch = self._branches[agent]
        # A resumed interrupt can deliver a tool end whose start was a turn ago.
        branch.pending_tools = max(branch.pending_tools - 1, 0)
        if event.data.get("status", "?") == "error":
            self._emit(
                agent,
                f"  {self._red}✗{self._reset}  [{agent}] tool error: {event.data.get('error')}\n",
            )
        else:
            self._emit(agent, f"  {self._green}✓{self._reset}  [{agent}] tool done\n")

    def _handle_agent_complete(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        usage = event.data.get("usage", {})
        in_tokens = usage.get("input_tokens", 0)
        out_tokens = usage.get("output_tokens", 0)
        self._emit(
            agent,
            f"  {self._dim}✅  [{agent}] complete  "
            f"({in_tokens} input, {out_tokens} output tokens){self._reset}\n",
        )
        self._end(agent)

    def _handle_interrupt(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        data = event.data
        name = data.get("name") or "—"
        reason = data.get("reason") or "no reason given"
        self._emit(
            agent,
            self._separator(agent, "INTERRUPT", color=self._yellow)
            + f"  {self._yellow}⏸{self._reset}  [{agent}] awaiting input for {name!r}: {reason}\n"
            + f"  {self._dim}interrupt_id: {data.get('interrupt_id') or '—'}{self._reset}\n",
        )

    def _handle_error(self, event: StreamEvent) -> None:
        agent = event.agent_name
        self._start_line(agent)
        msg = event.data.get("text", "unknown error")
        exc_type = event.data.get("exception_type")
        prefix = f"{exc_type}: " if exc_type else ""
        self._emit(
            agent,
            self._separator(agent, "ERROR", color=self._red)
            + f"  {self._red}✗  [{agent}] ERROR: {prefix}{msg}{self._reset}\n",
        )
        # An ERROR suppresses the agent's AGENT_COMPLETE, so nothing more follows.
        self._end(agent)

    def _handle_node_start(self, event: StreamEvent) -> None:
        self._write_direct(
            f"\n{self._cyan}->{self._reset}  node '{event.data.get('node_id')}'  starting\n"
        )

    def _handle_node_stop(self, event: StreamEvent) -> None:
        self._write_direct(
            f"{self._cyan}←{self._reset}  node '{event.data.get('node_id')}'  done\n"
        )

    def _handle_handoff(self, event: StreamEvent) -> None:
        to_ids = ", ".join(event.data.get("to_node_ids", []))
        self._write_direct(f"  {self._cyan}↪{self._reset}  handoff -> {to_ids}\n")

    def _handle_multiagent_start(self, event: StreamEvent) -> None:
        kind = event.data.get("multiagent_type", "")
        self._write_direct(f"\n{self._cyan}⊕{self._reset}  {kind} orchestration starting\n")

    def _handle_multiagent_complete(self, event: StreamEvent) -> None:
        kind = event.data.get("multiagent_type", "")
        self._write_direct(f"{self._cyan}⊗{self._reset}  {kind} orchestration complete\n\n")

    # -- Internal helpers --------------------------------------------------

    def _claim(self, agent: str) -> _Branch:
        """Give *agent* the terminal when it is free and return its state.

        An agent taking the terminal writes the backlog it built up while
        another agent was live, keeping its block contiguous.  An agent still
        waiting on tool calls is refused, so it cannot hold the terminal while
        the sub-agent it called is producing output.
        """
        branch = self._branches.setdefault(agent, _Branch())
        if self._owner is None and not branch.pending_tools:
            self._owner = agent
            self._write_buffer(agent)
        return branch

    def _start_line(self, agent: str) -> None:
        """Claim the terminal for *agent* and start a structured line.

        Closes an open stream and forces a fresh header on the next chunk.
        """
        self._claim(agent)
        self._break(agent)
        self._branches[agent].mode = None

    def _end(self, agent: str) -> None:
        """Mark *agent* finished and hand back the terminal it held."""
        self._branches[agent].ended = True
        self._release(agent)

    def _release(self, agent: str) -> None:
        """Free the terminal held by *agent* and write out the blocks now due.

        Finished blocks are written first, then the terminal goes to an agent
        that is mid-stream.  Without that hand-off an idle agent would claim it
        and the streaming agent would stay buffered and invisible.
        """
        if self._owner != agent:
            return
        self._owner = None
        for name, branch in self._branches.items():
            if branch.ended:
                self._write_buffer(name)
        for name, branch in self._branches.items():
            if not branch.ended and branch.in_stream:
                self._owner = name
                self._write_buffer(name)
                return

    def _emit(self, agent: str, text: str, *, stream: bool = False) -> None:
        """Write *text* for *agent*, buffering it while another agent is live.

        Args:
            agent: Agent the output belongs to.
            text: Rendered text to write.
            stream: Whether to apply the typewriter delay.  Whitespace and
                control characters are never delayed, to avoid stutter on word
                boundaries, and buffered blocks always replay at full speed.
        """
        if agent != self._owner:
            self._branches[agent].buffer.append(text)
            return
        if stream and self._typewriter_delay > 0.0:
            for char in text:
                self._out.write(char)
                self._out.flush()
                if char.isprintable() and not char.isspace():
                    time.sleep(self._typewriter_delay)
            return
        self._out.write(text)
        self._out.flush()

    def _write_direct(self, text: str) -> None:
        """Write *text* that belongs to no single agent, breaking the live stream."""
        if self._owner is not None:
            self._break(self._owner)
        self._out.write(text)
        self._out.flush()

    def _write_buffer(self, agent: str) -> None:
        """Write *agent*'s buffered block straight to the output stream."""
        branch = self._branches[agent]
        if not branch.buffer:
            return
        self._out.write("".join(branch.buffer))
        branch.buffer.clear()
        self._out.flush()

    def _break(self, agent: str) -> None:
        """Insert a newline if *agent* is mid-token/reasoning stream."""
        branch = self._branches[agent]
        if branch.in_stream:
            self._emit(agent, "\n")
            branch.in_stream = False

    def _separator(self, agent: str, label: str, color: str | None = None) -> str:
        """Build a separator line like ``── agent — REASONING ──``."""
        c = color if color is not None else self._dim
        inner = f" {agent} \u2014 {label} "
        pad = max(0, self._separator_width - len(inner) - 4)
        left = 2
        right = pad - left if pad > left else 0
        return f"\n{c}{'─' * left}{inner}{'─' * right}{self._reset}\n"

    def _ensure_mode(self, agent: str, mode: str) -> None:
        """Print a separator when *agent*'s mode changes."""
        branch = self._branches[agent]
        if branch.mode == mode:
            return
        self._break(agent)
        branch.mode = mode
        label = "REASONING" if mode == "reasoning" else "RESPONDING"
        color = self._yellow if mode == "reasoning" else self._cyan
        self._emit(agent, self._separator(agent, label, color=color))
