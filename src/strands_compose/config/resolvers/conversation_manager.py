"""Resolve ConversationManagerDef -> strands ConversationManager instance."""

from __future__ import annotations

from typing import TYPE_CHECKING

from strands.agent.conversation_manager import ConversationManager

from ...exceptions import ConfigurationError
from ...utils import load_object

if TYPE_CHECKING:
    from ..schema import ConversationManagerDef


def resolve_conversation_manager(cm_def: ConversationManagerDef) -> ConversationManager:
    """Resolve a ConversationManagerDef to a ConversationManager instance.

    ``type`` must be one of:

    - ``"module.path:ClassName"`` -- full import path (e.g.
      ``"strands.agent:SlidingWindowConversationManager"``)
    - ``"./path/to/file.py:ClassName"`` -- file-based import

    Args:
        cm_def: Conversation manager definition from YAML.

    Returns:
        Instantiated ConversationManager.

    Raises:
        ConfigurationError: If ``type`` is not in ``module:Class`` format.
        TypeError: If the resolved object is not a ConversationManager subclass.
    """
    type_str = cm_def.type
    if ":" not in type_str:
        raise ConfigurationError(
            f"Conversation manager type {type_str!r} is not a valid import spec.\n"
            f"Use 'module.path:ClassName' (e.g. "
            f"'strands.agent:SlidingWindowConversationManager') "
            f"or './path/to/file.py:ClassName'."
        )

    cls = load_object(type_str, target="conversation manager")

    manager = cls(**cm_def.params)
    if not isinstance(manager, ConversationManager):
        raise TypeError(
            f"Conversation manager {type_str!r} returned {type(manager).__name__}, "
            f"expected ConversationManager subclass."
        )
    return manager
