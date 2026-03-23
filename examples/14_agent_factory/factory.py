"""Custom agent factory for strands-compose.

A factory is any callable that receives the standard agent parameters
plus whatever you put in ``agent_kwargs`` and returns a ``strands.Agent``.

strands-compose calls it like::

    factory(
        name=...,
        agent_id=...,
        model=...,
        system_prompt=...,
        description=...,
        tools=...,
        hooks=...,
        session_manager=...,
        **agent_kwargs,
    )

⚠️  ``strands.Agent.__init__`` does NOT accept **kwargs — it has
explicit parameters only.  Your factory MUST consume any custom keys
from ``agent_kwargs`` before forwarding the rest to ``Agent()``.
"""

from __future__ import annotations

from strands import Agent


def create_agent(
    *,
    name: str,
    greeting: str = "Hello!",
    personality: str = "friendly",
    **kwargs,
) -> Agent:
    """Create an Agent with a personality injected into the system prompt.

    ``greeting`` and ``personality`` come from ``agent_kwargs`` in YAML.
    """
    # Extract and enhance system_prompt
    system_prompt = kwargs.pop("system_prompt", "") or ""
    enhanced_prompt = (
        f"{system_prompt}\n\n"
        f"Your personality is: {personality}.\n"
        f"Always start your first reply with: {greeting}"
    )

    return Agent(
        name=name,
        system_prompt=enhanced_prompt,
        **kwargs,
    )
