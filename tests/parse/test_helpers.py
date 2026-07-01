"""Parse-layer transforms: key sanitization, path rewriting, source parsing and merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from strands_compose.config.loaders.helpers import (
    is_fs_spec,
    make_absolute,
    merge_raw_configs,
    parse_single_source,
    sanitize_collection_keys,
    sanitize_name,
)
from tests.factories import write_config

# ── Key sanitization ──────────────────────────────────────────────────────


def test_sanitize_name_replaces_illegal_characters():
    assert sanitize_name("my agent!") == "my_agent"


def test_sanitize_name_truncates_to_64_chars():
    assert len(sanitize_name("a" * 200)) == 64


def test_sanitize_collection_keys_renames_and_updates_entry_reference():
    raw = {"agents": {"my agent": {"system_prompt": "hi"}}, "entry": "my agent"}
    sanitize_collection_keys(raw)
    assert "my_agent" in raw["agents"]
    assert raw["entry"] == "my_agent"


def test_sanitize_collection_keys_updates_model_and_mcp_references():
    raw = {
        "models": {"fast model": {"provider": "bedrock", "model_id": "m"}},
        "mcp_clients": {"db client": {"server": "db server"}},
        "mcp_servers": {"db server": {"type": "mod:make"}},
        "agents": {"a": {"model": "fast model", "mcp": ["db client"]}},
        "entry": "a",
    }
    sanitize_collection_keys(raw)
    assert raw["agents"]["a"]["model"] == "fast_model"
    assert raw["agents"]["a"]["mcp"] == ["db_client"]
    assert raw["mcp_clients"]["db_client"]["server"] == "db_server"


def test_sanitize_collection_keys_updates_orchestration_references():
    raw: dict = {
        "agents": {"the writer": {"system_prompt": "w"}},
        "orchestrations": {
            "team": {
                "mode": "delegate",
                "entry_name": "the writer",
                "connections": [{"agent": "the writer", "description": "d"}],
            }
        },
        "entry": "team",
    }
    sanitize_collection_keys(raw)
    orch: dict[str, Any] = raw["orchestrations"]["team"]
    assert orch["entry_name"] == "the_writer"
    assert orch["connections"][0]["agent"] == "the_writer"


# ── Filesystem spec detection & absolutization ─────────────────────────────


def test_is_fs_spec_detects_paths_and_rejects_module_specs():
    assert is_fs_spec("./tools/greet.py:greet")
    assert is_fs_spec("tools/greet.py")
    assert not is_fs_spec("my_package.tools:greet")


def test_make_absolute_rewrites_relative_file_spec():
    result = make_absolute("./tools/greet.py:greet", Path("/project/cfg"))
    assert result.startswith("/project/cfg/tools/greet.py:greet") or result.startswith("/")
    assert result.endswith(":greet")


def test_make_absolute_leaves_module_specs_unchanged():
    assert make_absolute("my_pkg.tools:fn", Path("/project")) == "my_pkg.tools:fn"


# ── Source parsing ─────────────────────────────────────────────────────────


def test_parse_single_source_reads_inline_yaml():
    raw = parse_single_source("agents:\n  a:\n    system_prompt: hi\nentry: a")
    assert raw["agents"]["a"]["system_prompt"] == "hi"


def test_parse_single_source_reads_file(tmp_path):
    path = write_config(tmp_path, "agents:\n  a:\n    system_prompt: hi\nentry: a")
    raw = parse_single_source(path)
    assert raw["entry"] == "a"


def test_parse_single_source_missing_file_raises_file_not_found():
    with pytest.raises(FileNotFoundError):
        parse_single_source("does/not/exist.yaml")


def test_parse_single_source_non_mapping_raises_value_error():
    with pytest.raises(ValueError):
        parse_single_source("- just\n- a\n- list")


def test_parse_single_source_rewrites_relative_tool_path_to_absolute(tmp_path):
    path = write_config(
        tmp_path,
        """
        agents:
          a:
            system_prompt: hi
            tools:
              - ./tools/greet.py:greet
        entry: a
        """,
    )
    raw = parse_single_source(path)
    tool_spec = raw["agents"]["a"]["tools"][0]
    assert Path(tool_spec.split(":")[0]).is_absolute()


def test_parse_single_source_applies_per_source_interpolation(tmp_path, monkeypatch):
    monkeypatch.delenv("PROMPT", raising=False)
    path = write_config(
        tmp_path,
        """
        vars:
          PROMPT: injected
        agents:
          a:
            system_prompt: ${PROMPT}
        entry: a
        """,
    )
    raw = parse_single_source(path)
    assert raw["agents"]["a"]["system_prompt"] == "injected"


# ── Multi-source merge ─────────────────────────────────────────────────────


def test_merge_combines_collection_sections():
    merged = merge_raw_configs(
        [
            {"agents": {"a": {"system_prompt": "x"}}, "entry": "a"},
            {"agents": {"b": {"system_prompt": "y"}}},
        ]
    )
    assert set(merged["agents"]) == {"a", "b"}


def test_merge_duplicate_name_in_same_section_raises():
    with pytest.raises(ValueError, match="Duplicate"):
        merge_raw_configs(
            [
                {"agents": {"a": {"system_prompt": "x"}}},
                {"agents": {"a": {"system_prompt": "y"}}},
            ]
        )


def test_merge_singleton_fields_use_last_wins():
    merged = merge_raw_configs([{"entry": "a"}, {"entry": "b"}])
    assert merged["entry"] == "b"
