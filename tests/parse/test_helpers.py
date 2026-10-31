"""Parse-layer transforms: key sanitization, path rewriting, source parsing and merge."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from strands_compose.config.loaders.helpers import (
    apply_mcp_stdio_cwd_default,
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


def test_sanitize_collection_keys_renames_and_updates_entry_reference():
    raw = {"agents": {"my agent": {"system_prompt": "hi"}}, "entry": "my agent"}
    sanitize_collection_keys(raw)
    assert "my_agent" in raw["agents"]
    assert raw["entry"] == "my_agent"


def test_sanitize_collection_keys_updates_model_and_mcp_references():
    raw = {
        "models": {"fast model": {"provider": "bedrock", "model_id": "m"}},
        "mcp_clients": {"db client": {"url": "https://example.com/mcp"}},
        "agents": {"a": {"model": "fast model", "mcp": ["db client"]}},
        "entry": "a",
    }
    sanitize_collection_keys(raw)
    assert raw["agents"]["a"]["model"] == "fast_model"
    assert raw["agents"]["a"]["mcp"] == ["db_client"]
    assert "db_client" in raw["mcp_clients"]


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


def test_make_absolute_rewrites_relative_file_spec(tmp_path):
    result = make_absolute("./tools/greet.py:greet", tmp_path)
    path_part, sep, attr = result.rpartition(":")
    assert sep == ":"
    assert attr == "greet"
    assert Path(path_part).is_absolute()


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


@pytest.mark.parametrize(
    "inline",
    [
        "agents:\n  a:\n    system_prompt: see http://example.com/docs\nentry: a",
        "agents:\n  a:\n    tools: [./tools.py]\nentry: a",
        "agents:\n  a:\n    system_prompt: " + "x" * 400 + "\nentry: a",
    ],
    ids=["url", "relative-import-spec", "over-255-characters"],
)
def test_parse_single_source_reads_multiline_inline_yaml_with_slash_or_long_text(inline):
    raw = parse_single_source(inline)
    assert raw["entry"] == "a"


def test_parse_single_source_overlong_single_line_text_is_parsed_inline():
    raw = parse_single_source("entry: " + "x" * 300)
    assert raw["entry"] == "x" * 300


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
    # Split on the LAST colon to avoid tripping on a Windows drive letter (C:\...).
    path_part, sep, _attr = tool_spec.rpartition(":")
    assert sep == ":"
    assert Path(path_part).is_absolute()


@pytest.mark.parametrize(
    ("body", "location", "file_name"),
    [
        (
            """
            agents:
              a:
                system_prompt: hi
                session_manager:
                  type: ./sm.py:SM
            entry: a
            """,
            lambda raw: raw["agents"]["a"]["session_manager"],
            "sm.py",
        ),
        (
            """
            agents:
              a:
                system_prompt: hi
                conversation_manager:
                  type: ./cm.py:CM
            entry: a
            """,
            lambda raw: raw["agents"]["a"]["conversation_manager"],
            "cm.py",
        ),
        (
            """
            agents:
              a:
                system_prompt: hi
            orchestrations:
              g:
                mode: swarm
                entry_name: a
                session_manager:
                  type: ./sm.py:SM
            entry: g
            """,
            lambda raw: raw["orchestrations"]["g"]["session_manager"],
            "sm.py",
        ),
    ],
    ids=["agent-session-manager", "agent-conversation-manager", "orchestration-session-manager"],
)
def test_parse_single_source_anchors_manager_spec_to_config_dir(
    tmp_path, body, location, file_name
):
    path = write_config(tmp_path, body)
    raw = parse_single_source(path)
    path_part, sep, _attr = location(raw)["type"].rpartition(":")
    assert sep == ":"
    assert Path(path_part) == (tmp_path / file_name).resolve()


def test_parse_single_source_anchors_structured_output_to_config_dir(tmp_path):
    path = write_config(
        tmp_path,
        """
        agents:
          a:
            system_prompt: hi
            structured_output:
              model: ./schemas.py:Forecast
        entry: a
        """,
    )
    raw = parse_single_source(path)
    path_part, sep, name = raw["agents"]["a"]["structured_output"]["model"].rpartition(":")
    assert (sep, name) == (":", "Forecast")
    assert Path(path_part) == (tmp_path / "schemas.py").resolve()


def test_parse_single_source_anchors_inline_model_provider_to_config_dir(tmp_path):
    path = write_config(
        tmp_path,
        """
        agents:
          a:
            system_prompt: hi
            model:
              provider: ./my_model.py:MyModel
              model_id: x
        entry: a
        """,
    )
    raw = parse_single_source(path)
    path_part, sep, name = raw["agents"]["a"]["model"]["provider"].rpartition(":")
    assert (sep, name) == (":", "MyModel")
    assert Path(path_part) == (tmp_path / "my_model.py").resolve()


def test_parse_single_source_leaves_module_manager_spec_unchanged(tmp_path):
    path = write_config(
        tmp_path,
        """
        agents:
          a:
            system_prompt: hi
            conversation_manager:
              type: strands.agent:SlidingWindowConversationManager
        entry: a
        """,
    )
    raw = parse_single_source(path)
    assert raw["agents"]["a"]["conversation_manager"]["type"] == (
        "strands.agent:SlidingWindowConversationManager"
    )


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


# ── MCP stdio cwd default ───────────────────────────────────────────────────


def test_apply_mcp_stdio_cwd_default_sets_cwd_for_command_client(tmp_path):
    raw = cast("dict[str, Any]", {"mcp_clients": {"calc": {"command": ["python", "server.py"]}}})
    apply_mcp_stdio_cwd_default(raw, tmp_path)
    assert raw["mcp_clients"]["calc"]["transport_options"]["cwd"] == str(tmp_path)


def test_apply_mcp_stdio_cwd_default_does_not_override_explicit_cwd(tmp_path):
    raw: dict[str, Any] = {
        "mcp_clients": {
            "calc": {
                "command": ["python", "server.py"],
                "transport_options": {"cwd": "/explicit/dir"},
            }
        }
    }
    apply_mcp_stdio_cwd_default(raw, tmp_path)
    assert raw["mcp_clients"]["calc"]["transport_options"]["cwd"] == "/explicit/dir"


def test_apply_mcp_stdio_cwd_default_leaves_url_client_untouched(tmp_path):
    raw: dict[str, Any] = {"mcp_clients": {"remote": {"url": "https://example.com/mcp"}}}
    apply_mcp_stdio_cwd_default(raw, tmp_path)
    assert "transport_options" not in raw["mcp_clients"]["remote"]


def test_apply_mcp_stdio_cwd_default_does_not_rewrite_command_itself(tmp_path):
    raw = cast(
        "dict[str, Any]",
        {"mcp_clients": {"fs": {"command": ["npx", "-y", "@scope/server", "/tmp"]}}},
    )
    apply_mcp_stdio_cwd_default(raw, tmp_path)
    assert raw["mcp_clients"]["fs"]["command"] == ["npx", "-y", "@scope/server", "/tmp"]
    assert raw["mcp_clients"]["fs"]["transport_options"]["cwd"] == str(tmp_path)


def test_parse_single_source_defaults_mcp_command_cwd_to_config_dir(tmp_path):
    path = write_config(
        tmp_path,
        """
        mcp_clients:
          calc:
            command: ["python", "server.py"]
        agents:
          a:
            system_prompt: hi
        entry: a
        """,
    )
    raw = parse_single_source(path)
    cwd = raw["mcp_clients"]["calc"]["transport_options"]["cwd"]
    assert Path(cwd) == tmp_path.resolve()


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
