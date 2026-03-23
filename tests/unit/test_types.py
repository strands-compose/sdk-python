"""Tests for the EventType StrEnum."""

from __future__ import annotations

from enum import StrEnum

import pytest

from strands_compose.types import EventType


class TestEventTypeEnum:
    """Verify EventType is a proper StrEnum with all expected members."""

    def test_is_str_enum_with_string_values(self):
        """EventType is a StrEnum and all members are strings."""
        assert issubclass(EventType, StrEnum)
        for member in EventType:
            assert isinstance(member, str)
            assert isinstance(member.value, str)

    @pytest.mark.parametrize(
        ("member", "expected_value"),
        [
            ("TOKEN", "token"),
            ("AGENT_START", "agent_start"),
            ("COMPLETE", "complete"),
            ("ERROR", "error"),
            ("TOOL_START", "tool_start"),
            ("TOOL_END", "tool_end"),
            ("REASONING", "reasoning"),
            ("NODE_START", "node_start"),
            ("NODE_STOP", "node_stop"),
            ("HANDOFF", "handoff"),
            ("MULTIAGENT_START", "multiagent_start"),
            ("MULTIAGENT_COMPLETE", "multiagent_complete"),
        ],
    )
    def test_string_comparison_works(self, member, expected_value):
        """StrEnum values compare equal to their plain string counterparts."""
        assert EventType[member] == expected_value

    def test_all_members_present(self):
        expected = {
            "AGENT_START",
            "TOKEN",
            "TOOL_START",
            "TOOL_END",
            "REASONING",
            "COMPLETE",
            "ERROR",
            "NODE_START",
            "NODE_STOP",
            "HANDOFF",
            "MULTIAGENT_START",
            "MULTIAGENT_COMPLETE",
        }
        assert set(EventType.__members__) == expected
