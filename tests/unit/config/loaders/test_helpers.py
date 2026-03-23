"""Tests for config.loaders.helpers — sanitize, path rewriting, merge."""

from __future__ import annotations

from pathlib import Path

from strands_compose.config.loaders.helpers import (
    is_fs_spec,
    make_absolute,
    rewrite_relative_paths,
    sanitize_name,
)


class TestSanitizeName:
    """Unit tests for the sanitize_name helper."""

    def test_spaces_to_underscores(self):
        assert sanitize_name("Database Analyzer") == "Database_Analyzer"

    def test_special_chars_replaced(self):
        assert sanitize_name("my.agent@v2") == "my_agent_v2"

    def test_consecutive_underscores_collapsed(self):
        assert sanitize_name("a   b") == "a_b"

    def test_leading_trailing_stripped(self):
        assert sanitize_name(" hello ") == "hello"

    def test_hyphens_preserved(self):
        assert sanitize_name("my-agent") == "my-agent"

    def test_valid_name_unchanged(self):
        assert sanitize_name("valid_name") == "valid_name"

    def test_truncation_to_64(self):
        long_name = "a" * 100
        assert len(sanitize_name(long_name)) == 64

    def test_empty_result(self):
        assert sanitize_name("...") == ""


class TestIsFsSpec:
    def test_relative_file(self):
        assert is_fs_spec("./tools.py") is True

    def test_relative_file_with_function(self):
        assert is_fs_spec("./tools.py:my_func") is True

    def test_relative_directory(self):
        assert is_fs_spec("./my_tools/") is True

    def test_module_spec(self):
        assert is_fs_spec("my_package:my_func") is False

    def test_bare_module(self):
        assert is_fs_spec("strands_tools") is False

    def test_absolute_path(self):
        assert is_fs_spec("/abs/path/tools.py") is True

    def test_backslash_path(self):
        assert is_fs_spec(".\\tools.py:func") is True


class TestMakeAbsolute:
    def test_relative_file_becomes_absolute(self, tmp_path: Path):
        result = make_absolute("./tools.py", tmp_path)
        assert Path(result).is_absolute()
        assert result == str((tmp_path / "tools.py").resolve())

    def test_relative_file_with_function(self, tmp_path: Path):
        result = make_absolute("./tools.py:func", tmp_path)
        assert result == f"{(tmp_path / 'tools.py').resolve()}:func"

    def test_absolute_path_unchanged(self, tmp_path: Path):
        result = make_absolute("/abs/tools.py", tmp_path)
        assert result == "/abs/tools.py"

    def test_module_spec_unchanged(self, tmp_path: Path):
        result = make_absolute("my_package:my_func", tmp_path)
        assert result == "my_package:my_func"

    def test_relative_directory(self, tmp_path: Path):
        result = make_absolute("./my_tools/", tmp_path)
        assert Path(result).is_absolute()


class TestRewriteRelativePaths:
    # ── agents.tools ──────────────────────────────────────────────────────
    def test_tool_relative_file(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"tools": ["./tools.py"]}}}
        rewrite_relative_paths(raw, tmp_path)
        assert Path(raw["agents"]["a"]["tools"][0]).is_absolute()

    def test_tool_relative_with_function(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"tools": ["./tools.py:my_func"]}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["agents"]["a"]["tools"][0]
        assert ":my_func" in result
        assert Path(result.rpartition(":")[0]).is_absolute()

    def test_tool_module_spec_unchanged(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"tools": ["my_package:my_func"]}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["agents"]["a"]["tools"][0] == "my_package:my_func"

    def test_tool_absolute_unchanged(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"tools": ["/abs/tools.py"]}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["agents"]["a"]["tools"][0] == "/abs/tools.py"

    # ── agents.hooks ──────────────────────────────────────────────────────
    def test_hook_string_spec_rewritten(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"hooks": ["./hooks.py:MyHook"]}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["agents"]["a"]["hooks"][0]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":MyHook")

    def test_hook_dict_type_rewritten(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"hooks": [{"type": "./hooks.py:Guard", "params": {}}]}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["agents"]["a"]["hooks"][0]["type"]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":Guard")

    def test_hook_module_spec_unchanged(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"hooks": ["strands_compose.hooks:StopGuard"]}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["agents"]["a"]["hooks"][0] == "strands_compose.hooks:StopGuard"

    # ── agents.type ───────────────────────────────────────────────────────
    def test_agent_type_rewritten(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"type": "./factory.py:CustomAgent"}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["agents"]["a"]["type"]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":CustomAgent")

    def test_agent_type_module_unchanged(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"type": "my_pkg.agents:Custom"}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["agents"]["a"]["type"] == "my_pkg.agents:Custom"

    # ── mcp_servers.type ──────────────────────────────────────────────────
    def test_mcp_server_type_rewritten(self, tmp_path: Path):
        raw: dict = {"mcp_servers": {"pg": {"type": "./server.py:create"}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["mcp_servers"]["pg"]["type"]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":create")

    def test_mcp_server_module_unchanged(self, tmp_path: Path):
        raw: dict = {"mcp_servers": {"pg": {"type": "my_pkg:create"}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["mcp_servers"]["pg"]["type"] == "my_pkg:create"

    # ── models.provider ───────────────────────────────────────────────────
    def test_model_provider_file_rewritten(self, tmp_path: Path):
        raw: dict = {"models": {"custom": {"provider": "./models.py:MyModel", "model_id": "x"}}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["models"]["custom"]["provider"]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":MyModel")

    def test_model_builtin_provider_unchanged(self, tmp_path: Path):
        raw: dict = {"models": {"m": {"provider": "bedrock", "model_id": "x"}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["models"]["m"]["provider"] == "bedrock"

    # ── session_manager.type ──────────────────────────────────────────────
    def test_session_manager_type_rewritten(self, tmp_path: Path):
        raw: dict = {"session_manager": {"type": "./session.py:CustomSM"}}
        rewrite_relative_paths(raw, tmp_path)
        result = raw["session_manager"]["type"]
        assert Path(result.rpartition(":")[0]).is_absolute()
        assert result.endswith(":CustomSM")

    def test_session_manager_module_type_unchanged(self, tmp_path: Path):
        raw: dict = {"session_manager": {"type": "my_pkg:CustomSM"}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw["session_manager"]["type"] == "my_pkg:CustomSM"

    # ── orchestrations hooks ──────────────────────────────────────────────
    def test_orchestration_hooks_rewritten(self, tmp_path: Path):
        raw: dict = {
            "orchestrations": {
                "main": {
                    "mode": "swarm",
                    "hooks": [
                        "./hooks.py:Guard",
                        {"type": "./hooks.py:Logger", "params": {}},
                    ],
                }
            }
        }
        rewrite_relative_paths(raw, tmp_path)
        hooks = raw["orchestrations"]["main"]["hooks"]
        hook_str = hooks[0]
        assert isinstance(hook_str, str)
        assert Path(hook_str.rpartition(":")[0]).is_absolute()
        hook_dict = hooks[1]
        assert isinstance(hook_dict, dict)
        hook_type_val = hook_dict["type"]
        assert isinstance(hook_type_val, str)
        assert Path(hook_type_val.rpartition(":")[0]).is_absolute()

    # ── empty / missing sections ──────────────────────────────────────────
    def test_empty_raw_is_noop(self, tmp_path: Path):
        raw: dict = {}
        rewrite_relative_paths(raw, tmp_path)
        assert raw == {}

    def test_agent_without_tools_unchanged(self, tmp_path: Path):
        raw: dict = {"agents": {"a": {"system_prompt": "hi"}}}
        rewrite_relative_paths(raw, tmp_path)
        assert raw == {"agents": {"a": {"system_prompt": "hi"}}}
