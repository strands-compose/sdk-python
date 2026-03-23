"""Tests for config.resolvers.conversation_manager — resolve_conversation_manager."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from strands.agent import (
    ConversationManager,
    NullConversationManager,
    SlidingWindowConversationManager,
    SummarizingConversationManager,
)

from strands_compose.config.resolvers.conversation_manager import resolve_conversation_manager
from strands_compose.config.schema import ConversationManagerDef


class TestResolveConversationManager:
    """Tests for resolve_conversation_manager()."""

    def test_sliding_window_default_params(self) -> None:
        """SlidingWindowConversationManager with default params."""
        cm_def = ConversationManagerDef(
            type="strands.agent:SlidingWindowConversationManager",
        )
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, SlidingWindowConversationManager)

    def test_sliding_window_custom_params(self) -> None:
        """SlidingWindowConversationManager with custom params forwarded."""
        cm_def = ConversationManagerDef(
            type="strands.agent:SlidingWindowConversationManager",
            params={"window_size": 20, "should_truncate_results": False},
        )
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, SlidingWindowConversationManager)
        assert result.window_size == 20
        assert result.should_truncate_results is False

    def test_null_conversation_manager(self) -> None:
        """NullConversationManager with no params."""
        cm_def = ConversationManagerDef(
            type="strands.agent:NullConversationManager",
        )
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, NullConversationManager)

    def test_summarizing_conversation_manager(self) -> None:
        """SummarizingConversationManager with default params."""
        cm_def = ConversationManagerDef(
            type="strands.agent:SummarizingConversationManager",
        )
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, SummarizingConversationManager)

    def test_summarizing_with_custom_params(self) -> None:
        """SummarizingConversationManager forwards custom params."""
        cm_def = ConversationManagerDef(
            type="strands.agent:SummarizingConversationManager",
            params={"summary_ratio": 0.5, "preserve_recent_messages": 5},
        )
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, SummarizingConversationManager)
        assert result.summary_ratio == 0.5
        assert result.preserve_recent_messages == 5

    def test_no_colon_raises_value_error(self) -> None:
        """Type string without colon separator raises ValueError."""
        cm_def = ConversationManagerDef(type="not_a_valid_spec")
        with pytest.raises(ValueError, match="not a valid import spec"):
            resolve_conversation_manager(cm_def)

    @patch("strands_compose.config.resolvers.conversation_manager.load_object")
    def test_non_conversation_manager_raises_type_error(self, mock_load: MagicMock) -> None:
        """Resolved class that is not a ConversationManager raises TypeError."""
        mock_load.return_value = MagicMock(return_value="not_a_manager")
        cm_def = ConversationManagerDef(type="some.module:BadClass")
        with pytest.raises(TypeError, match="expected ConversationManager subclass"):
            resolve_conversation_manager(cm_def)

    def test_file_based_conversation_manager(self, tmp_path: object) -> None:
        """File-based import path resolves a custom ConversationManager."""
        import pathlib

        tmp = pathlib.Path(str(tmp_path))
        cm_file = tmp / "my_cm.py"
        cm_file.write_text(
            "from strands.agent.conversation_manager import ConversationManager\n"
            "from typing import Any\n"
            "class MyCM(ConversationManager):\n"
            "    def __init__(self, x: int = 1) -> None:\n"
            "        self.x = x\n"
            "    def apply_management(self, agent: Any, **kwargs: Any) -> None:\n"
            "        pass\n"
            "    def reduce_context(self, agent: Any, e: Exception | None = None, **kwargs: Any) -> None:\n"
            "        pass\n"
        )
        cm_def = ConversationManagerDef(type=f"{cm_file}:MyCM", params={"x": 42})
        result = resolve_conversation_manager(cm_def)
        assert isinstance(result, ConversationManager)
        assert result.x == 42  # type: ignore[unresolved-attribute]

    @patch("strands_compose.config.resolvers.conversation_manager.load_object")
    def test_params_forwarded_to_constructor(self, mock_load: MagicMock) -> None:
        """Params dict is spread as kwargs to the resolved class."""
        mock_cls = MagicMock()
        mock_instance = MagicMock(spec=ConversationManager)
        mock_cls.return_value = mock_instance
        mock_load.return_value = mock_cls

        cm_def = ConversationManagerDef(
            type="some.module:CustomCM",
            params={"window_size": 10, "custom_flag": True},
        )
        result = resolve_conversation_manager(cm_def)

        mock_cls.assert_called_once_with(window_size=10, custom_flag=True)
        assert result is mock_instance
