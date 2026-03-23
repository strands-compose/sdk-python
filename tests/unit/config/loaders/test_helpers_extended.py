"""Tests for config.loaders.helpers — sanitize_collection_keys, update_references,
parse_single_source, merge_raw_configs.

These are focused unit tests for functions that previously only had indirect
coverage via load_config() integration tests.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strands_compose.config.loaders.helpers import (
    merge_raw_configs,
    parse_single_source,
    sanitize_collection_keys,
    update_references,
)
from strands_compose.exceptions import ConfigurationError

# ── sanitize_collection_keys ──────────────────────────────────────────────


class TestSanitizeCollectionKeys:
    """Unit tests for sanitize_collection_keys()."""

    def test_valid_keys_unchanged(self):
        raw: dict = {"agents": {"valid_name": {"system_prompt": "hi"}}}
        sanitize_collection_keys(raw)
        assert "valid_name" in raw["agents"]

    def test_spaces_to_underscores(self):
        raw: dict = {"agents": {"My Agent": {"system_prompt": "hi"}}}
        sanitize_collection_keys(raw)
        assert "My_Agent" in raw["agents"]
        assert "My Agent" not in raw["agents"]

    def test_special_chars_sanitized(self):
        raw: dict = {"agents": {"my.agent@v2": {"system_prompt": "hi"}}}
        sanitize_collection_keys(raw)
        assert "my_agent_v2" in raw["agents"]

    def test_duplicate_after_sanitization_raises(self):
        raw: dict = {
            "agents": {
                "my agent": {"system_prompt": "a"},
                "my_agent": {"system_prompt": "b"},
            }
        }
        with pytest.raises(ValueError, match="Duplicate name.*after sanitization"):
            sanitize_collection_keys(raw)

    def test_empty_after_sanitization_raises(self):
        raw: dict = {"agents": {"...": {"system_prompt": "hi"}}}
        with pytest.raises(ValueError, match="empty after sanitization"):
            sanitize_collection_keys(raw)

    def test_models_section_sanitized(self):
        raw: dict = {"models": {"My Model": {"provider": "bedrock", "model_id": "x"}}}
        sanitize_collection_keys(raw)
        assert "My_Model" in raw["models"]

    def test_mcp_servers_section_sanitized(self):
        raw: dict = {"mcp_servers": {"My Server": {"type": "stdio"}}}
        sanitize_collection_keys(raw)
        assert "My_Server" in raw["mcp_servers"]

    def test_non_dict_section_skipped(self):
        raw: dict = {"agents": "not-a-dict"}
        sanitize_collection_keys(raw)
        assert raw["agents"] == "not-a-dict"

    def test_missing_section_ignored(self):
        raw: dict = {"entry": "a"}
        sanitize_collection_keys(raw)
        assert raw == {"entry": "a"}

    def test_calls_update_references_when_renamed(self):
        raw: dict = {
            "agents": {"My Agent": {"system_prompt": "hi"}},
            "entry": "My Agent",
        }
        sanitize_collection_keys(raw)
        assert raw["entry"] == "My_Agent"

    def test_preserves_definition_values(self):
        raw: dict = {"agents": {"My Agent": {"system_prompt": "hello", "max_tool_calls": 5}}}
        sanitize_collection_keys(raw)
        assert raw["agents"]["My_Agent"]["system_prompt"] == "hello"
        assert raw["agents"]["My_Agent"]["max_tool_calls"] == 5


# ── update_references ─────────────────────────────────────────────────────


class TestUpdateReferences:
    """Unit tests for update_references()."""

    def test_entry_reference_updated(self):
        raw: dict = {"entry": "Old Name"}
        update_references(raw, {"Old Name": "Old_Name"})
        assert raw["entry"] == "Old_Name"

    def test_entry_not_in_map_unchanged(self):
        raw: dict = {"entry": "unchanged"}
        update_references(raw, {"other": "other_renamed"})
        assert raw["entry"] == "unchanged"

    def test_agent_model_ref_updated(self):
        raw: dict = {"agents": {"a": {"model": "My Model"}}}
        update_references(raw, {"My Model": "My_Model"})
        assert raw["agents"]["a"]["model"] == "My_Model"

    def test_agent_mcp_refs_updated(self):
        raw: dict = {"agents": {"a": {"mcp": ["Client One", "client_two"]}}}
        update_references(raw, {"Client One": "Client_One"})
        assert raw["agents"]["a"]["mcp"] == ["Client_One", "client_two"]

    def test_mcp_client_server_ref_updated(self):
        raw: dict = {"mcp_clients": {"c": {"server": "My Server"}}}
        update_references(raw, {"My Server": "My_Server"})
        assert raw["mcp_clients"]["c"]["server"] == "My_Server"

    def test_delegate_connections_updated(self):
        raw: dict = {
            "orchestrations": {
                "main": {
                    "mode": "delegate",
                    "entry_name": "Parent Agent",
                    "connections": [
                        {"agent": "Child Agent", "description": "does stuff"},
                    ],
                }
            }
        }
        update_references(
            raw,
            {"Parent Agent": "Parent_Agent", "Child Agent": "Child_Agent"},
        )
        orch: dict = raw["orchestrations"]["main"]
        assert orch["entry_name"] == "Parent_Agent"
        conns: list = orch["connections"]  # type: ignore[assignment]
        assert conns[0]["agent"] == "Child_Agent"

    def test_swarm_refs_updated(self):
        raw: dict = {
            "orchestrations": {
                "main": {
                    "mode": "swarm",
                    "entry_name": "Agent A",
                    "agents": ["Agent A", "Agent B"],
                }
            }
        }
        update_references(raw, {"Agent A": "Agent_A", "Agent B": "Agent_B"})
        orch = raw["orchestrations"]["main"]
        assert orch["entry_name"] == "Agent_A"
        assert orch["agents"] == ["Agent_A", "Agent_B"]

    def test_graph_refs_updated(self):
        raw: dict = {
            "orchestrations": {
                "main": {
                    "mode": "graph",
                    "entry_name": "Node A",
                    "edges": [
                        {"from": "Node A", "to": "Node B"},
                    ],
                }
            }
        }
        update_references(raw, {"Node A": "Node_A", "Node B": "Node_B"})
        orch = raw["orchestrations"]["main"]
        assert orch["entry_name"] == "Node_A"
        edges = orch["edges"]
        assert edges[0]["from"] == "Node_A"  # type: ignore[index]
        assert edges[0]["to"] == "Node_B"  # type: ignore[index]

    def test_non_dict_agent_def_skipped(self):
        raw: dict = {"agents": {"a": "not-a-dict"}}
        update_references(raw, {"x": "y"})
        assert raw["agents"]["a"] == "not-a-dict"

    def test_non_dict_client_def_skipped(self):
        raw: dict = {"mcp_clients": {"c": "not-a-dict"}}
        update_references(raw, {"x": "y"})
        assert raw["mcp_clients"]["c"] == "not-a-dict"

    def test_non_dict_orch_def_skipped(self):
        raw: dict = {"orchestrations": {"main": "not-a-dict"}}
        update_references(raw, {"x": "y"})
        assert raw["orchestrations"]["main"] == "not-a-dict"

    def test_empty_rename_map_noop(self):
        raw: dict = {"entry": "a", "agents": {"a": {"model": "m"}}}
        original = {"entry": "a", "agents": {"a": {"model": "m"}}}
        update_references(raw, {})
        assert raw == original


# ── parse_single_source ───────────────────────────────────────────────────


class TestParseSingleSource:
    """Unit tests for parse_single_source()."""

    def test_parse_yaml_string(self):
        raw = parse_single_source("agents:\n  a:\n    system_prompt: hi\nentry: a\n")
        assert "agents" in raw
        assert raw["agents"]["a"]["system_prompt"] == "hi"

    def test_parse_path_object(self, tmp_path: Path):
        f = tmp_path / "config.yaml"
        f.write_text("agents:\n  a:\n    system_prompt: hi\nentry: a\n")
        raw = parse_single_source(f)
        assert raw["agents"]["a"]["system_prompt"] == "hi"

    def test_parse_file_string(self, tmp_path: Path):
        f = tmp_path / "config.yaml"
        f.write_text("agents:\n  a:\n    system_prompt: hi\nentry: a\n")
        raw = parse_single_source(str(f))
        assert raw["agents"]["a"]["system_prompt"] == "hi"

    def test_path_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            parse_single_source(Path("/nonexistent/config.yaml"))

    def test_string_looks_like_file_raises(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            parse_single_source("/nonexistent/config.yaml")

    def test_yaml_extension_string_not_found_raises(self):
        with pytest.raises(FileNotFoundError, match="Config file not found"):
            parse_single_source("missing.yaml")

    def test_non_dict_yaml_raises(self):
        with pytest.raises(ValueError, match="YAML mapping"):
            parse_single_source("just a string\n")

    def test_invalid_yaml_in_file_raises_configuration_error(self, tmp_path: Path):
        f = tmp_path / "bad.yaml"
        f.write_text("key: [unclosed\n")
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            parse_single_source(f)

    def test_invalid_yaml_inline_raises_configuration_error(self):
        with pytest.raises(ConfigurationError, match="Invalid YAML"):
            parse_single_source("key: [unclosed\n")

    def test_vars_block_stripped(self):
        raw = parse_single_source(
            "vars:\n  X: hello\nagents:\n  a:\n    system_prompt: '${X}'\nentry: a\n"
        )
        assert "vars" not in raw
        assert raw["agents"]["a"]["system_prompt"] == "hello"

    def test_anchors_stripped(self):
        raw = parse_single_source(
            "x-base: &base\n  system_prompt: shared\nagents:\n  a:\n    <<: *base\nentry: a\n"
        )
        assert "x-base" not in raw
        assert raw["agents"]["a"]["system_prompt"] == "shared"

    def test_relative_paths_rewritten(self, tmp_path: Path):
        f = tmp_path / "config.yaml"
        f.write_text(
            "agents:\n  a:\n    tools:\n      - ./tools.py\n    system_prompt: hi\nentry: a\n"
        )
        raw = parse_single_source(f)
        tool_path = raw["agents"]["a"]["tools"][0]
        assert Path(tool_path).is_absolute()

    def test_env_var_interpolation(self, monkeypatch, tmp_path: Path):
        monkeypatch.setenv("TEST_PROMPT_VALUE", "from-env")
        raw = parse_single_source(
            "agents:\n  a:\n    system_prompt: '${TEST_PROMPT_VALUE}'\nentry: a\n"
        )
        assert raw["agents"]["a"]["system_prompt"] == "from-env"


# ── merge_raw_configs ─────────────────────────────────────────────────────


class TestMergeRawConfigs:
    """Unit tests for merge_raw_configs()."""

    def test_merge_two_agent_configs(self):
        c1 = {"agents": {"a": {"system_prompt": "hi"}}, "entry": "a"}
        c2 = {"agents": {"b": {"system_prompt": "bye"}}}
        merged = merge_raw_configs([c1, c2])
        assert "a" in merged["agents"]
        assert "b" in merged["agents"]

    def test_duplicate_names_raises(self):
        c1 = {"agents": {"dupe": {"system_prompt": "first"}}}
        c2 = {"agents": {"dupe": {"system_prompt": "second"}}}
        with pytest.raises(ValueError, match="Duplicate names in 'agents'"):
            merge_raw_configs([c1, c2])

    def test_singleton_last_wins(self):
        c1 = {"agents": {"a": {}}, "entry": "a", "log_level": "DEBUG"}
        c2 = {"agents": {"b": {}}, "log_level": "ERROR"}
        merged = merge_raw_configs([c1, c2])
        assert merged["log_level"] == "ERROR"

    def test_empty_collections_removed(self):
        c1 = {"agents": {"a": {}}, "entry": "a"}
        merged = merge_raw_configs([c1])
        # models, mcp_servers, mcp_clients, orchestrations should not be present
        assert "models" not in merged
        assert "mcp_servers" not in merged
        assert "mcp_clients" not in merged
        assert "orchestrations" not in merged

    def test_merge_models_and_agents(self):
        c1 = {"models": {"m": {"provider": "bedrock", "model_id": "x"}}}
        c2 = {"agents": {"a": {}}, "entry": "a"}
        merged = merge_raw_configs([c1, c2])
        assert "m" in merged["models"]
        assert "a" in merged["agents"]

    def test_non_dict_section_ignored(self):
        c1 = {"agents": "not-a-dict", "entry": "a"}
        c2 = {"agents": {"b": {}}}
        merged = merge_raw_configs([c1, c2])
        assert "b" in merged["agents"]

    def test_merge_three_configs(self):
        c1 = {"agents": {"a": {}}}
        c2 = {"agents": {"b": {}}}
        c3 = {"agents": {"c": {}}, "entry": "a"}
        merged = merge_raw_configs([c1, c2, c3])
        assert set(merged["agents"]) == {"a", "b", "c"}

    def test_merge_mcp_sections(self):
        c1 = {"mcp_servers": {"s1": {"type": "stdio"}}}
        c2 = {"mcp_clients": {"c1": {"server": "s1"}}}
        merged = merge_raw_configs([c1, c2])
        assert "s1" in merged["mcp_servers"]
        assert "c1" in merged["mcp_clients"]

    def test_merge_orchestrations(self):
        c1 = {"orchestrations": {"orch1": {"mode": "swarm"}}}
        c2 = {"orchestrations": {"orch2": {"mode": "graph"}}}
        merged = merge_raw_configs([c1, c2])
        assert "orch1" in merged["orchestrations"]
        assert "orch2" in merged["orchestrations"]
