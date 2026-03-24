"""Unit tests for the strands-compose CLI (cli.py)."""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from strands_compose.cli import _build_parser, _cmd_check, _cmd_load
from strands_compose.startup.report import CheckResult, StartupReport

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mock_app_config(
    agents: dict | None = None,
    models: dict | None = None,
    mcp_clients: dict | None = None,
    mcp_servers: dict | None = None,
    orchestrations: dict | None = None,
    entry: str = "agent1",
    session_manager: MagicMock | None = None,
) -> MagicMock:
    """Return a minimal mock AppConfig."""
    cfg = MagicMock()
    cfg.agents = agents if agents is not None else {"agent1": MagicMock(hooks=[])}
    cfg.models = models if models is not None else {}
    cfg.mcp_clients = mcp_clients if mcp_clients is not None else {}
    cfg.mcp_servers = mcp_servers if mcp_servers is not None else {}
    cfg.orchestrations = orchestrations if orchestrations is not None else {}
    cfg.entry = entry
    cfg.session_manager = session_manager
    return cfg


def _mock_resolved() -> MagicMock:
    """Return a minimal mock ResolvedConfig with a stoppable mcp_lifecycle."""
    resolved = MagicMock()
    resolved.mcp_lifecycle.stop = MagicMock()
    return resolved


# ---------------------------------------------------------------------------
# check – argument parser
# ---------------------------------------------------------------------------


def test_build_parser_check_subcommand_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args(["check", "config.yaml"])
    assert args.command == "check"
    assert args.config == ["config.yaml"]
    assert args.json_output is False
    assert args.quiet is False


def test_build_parser_check_subcommand_with_json_flag() -> None:
    parser = _build_parser()
    args = parser.parse_args(["check", "config.yaml", "--json"])
    assert args.json_output is True


def test_build_parser_load_subcommand_defaults() -> None:
    parser = _build_parser()
    args = parser.parse_args(["load", "my.yaml"])
    assert args.command == "load"
    assert args.config == ["my.yaml"]
    assert args.json_output is False
    assert args.quiet is False


def test_build_parser_load_subcommand_with_json_flag() -> None:
    parser = _build_parser()
    args = parser.parse_args(["load", "my.yaml", "--json"])
    assert args.json_output is True


def test_build_parser_no_subcommand_exits() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


# ---------------------------------------------------------------------------
# check – success paths
# ---------------------------------------------------------------------------


def test_check_success_ansi_contains_valid_marker(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "Config valid" in out


def test_check_success_ansi_shows_entry_and_agent_names(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config(
        agents={"alpha": MagicMock(hooks=[]), "beta": MagicMock(hooks=[])},
        entry="alpha",
    )
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "alpha" in out
    assert "beta" in out


def test_check_success_ansi_shows_mcp_clients_when_present(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config(
        mcp_clients={"pg": MagicMock()},
        models={"bedrock": MagicMock()},
    )
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "pg" in out
    assert "bedrock" in out


def test_check_success_json_emits_valid_json(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config(entry="agent1", agents={"agent1": MagicMock(hooks=[])})
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["stage"] == "check"
    assert data["entry"] == "agent1"
    assert "agent1" in data["agents"]


def test_check_success_json_contains_all_section_keys(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    for key in ("agents", "models", "mcp_clients", "mcp_servers", "orchestrations"):
        assert key in data


# ---------------------------------------------------------------------------
# check – failure paths
# ---------------------------------------------------------------------------


def test_check_failure_exits_with_code_one() -> None:
    with patch("strands_compose.cli.load_config", side_effect=ValueError("bad field")):
        with pytest.raises(SystemExit) as exc_info:
            _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    assert exc_info.value.code == 1


def test_check_file_not_found_exits_with_code_one() -> None:
    with patch("strands_compose.cli.load_config", side_effect=FileNotFoundError("no file")):
        with pytest.raises(SystemExit) as exc_info:
            _cmd_check(["nonexistent.yaml"], json_output=False, quiet=False)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# load – success paths
# ---------------------------------------------------------------------------


def test_load_success_ansi_prints_ok(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[CheckResult.passed("network", "mcp:s1", "reachable")])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "Load OK" in out


def test_load_success_ansi_shows_passed_check(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[CheckResult.passed("network", "mcp:postgres", "reachable")])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "mcp:postgres" in out
    assert "reachable" in out


def test_load_success_with_no_mcp_shows_no_mcp_configured(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "Load OK" in out


def test_load_success_json_emits_valid_json(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[CheckResult.passed("network", "mcp:s1", "OK")])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is True
    assert data["stage"] == "load"
    assert len(data["checks"]) == 1
    assert data["checks"][0]["subject"] == "mcp:s1"


def test_load_success_json_check_fields_are_complete(capsys: pytest.CaptureFixture) -> None:
    check = CheckResult.passed("runtime", "mcp-client:pg", "session active")
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    entry = data["checks"][0]
    for key in ("ok", "category", "subject", "message", "severity", "hint"):
        assert key in entry


# ---------------------------------------------------------------------------
# load – failure paths
# ---------------------------------------------------------------------------


def test_load_critical_check_exits_with_code_one() -> None:
    check = CheckResult.critical("network", "mcp:s1", "connection refused")
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
        pytest.raises(SystemExit) as exc_info,
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    assert exc_info.value.code == 1


def test_load_critical_check_ansi_shows_failed_marker(capsys: pytest.CaptureFixture) -> None:
    check = CheckResult.critical(
        "network", "mcp:s1", "connection refused", hint="Is the server running?"
    )
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
        pytest.raises(SystemExit),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "Load FAILED" in out
    assert "Is the server running?" in out


def test_load_load_failure_exits_with_code_one() -> None:
    with (
        patch("strands_compose.cli.load", side_effect=ValueError("import failed")),
        pytest.raises(SystemExit) as exc_info,
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    assert exc_info.value.code == 1


def test_load_warning_check_exits_with_code_zero(capsys: pytest.CaptureFixture) -> None:
    check = CheckResult.warn("runtime", "mcp-client:pg", "session check failed")
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "Load OK" in out


def test_load_critical_json_has_ok_false(capsys: pytest.CaptureFixture) -> None:
    check = CheckResult.critical("network", "mcp:s1", "refused")
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
        pytest.raises(SystemExit),
    ):
        _cmd_load(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    assert data["ok"] is False


# ---------------------------------------------------------------------------
# load – lifecycle cleanup
# ---------------------------------------------------------------------------


def test_load_always_stops_mcp_lifecycle_on_validate_error() -> None:
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(side_effect=RuntimeError("boom"))),
        pytest.raises(RuntimeError),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    resolved.mcp_lifecycle.stop.assert_called_once()


def test_load_stops_mcp_lifecycle_on_success() -> None:
    report = StartupReport(checks=[])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    resolved.mcp_lifecycle.stop.assert_called_once()


def test_load_does_not_raise_attribute_error_when_load_fails() -> None:
    # When load() raises, resolved stays None; the finally block must not
    # attempt to call stop() on None (would raise AttributeError).
    with (
        patch("strands_compose.cli.load", side_effect=ValueError("bad")),
        pytest.raises(SystemExit) as exc_info,
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=False)
    assert exc_info.value.code == 1


# ---------------------------------------------------------------------------
# --version flag
# ---------------------------------------------------------------------------


def test_version_flag_exits_zero() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["--version"])
    assert exc_info.value.code == 0


def test_short_version_flag_exits_zero() -> None:
    parser = _build_parser()
    with pytest.raises(SystemExit) as exc_info:
        parser.parse_args(["-V"])
    assert exc_info.value.code == 0


# ---------------------------------------------------------------------------
# --quiet flag
# ---------------------------------------------------------------------------


def test_check_quiet_suppresses_output(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=True)
    out = capsys.readouterr().out
    assert out == ""


def test_check_quiet_with_json_suppresses_output(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=True, quiet=True)
    out = capsys.readouterr().out
    assert out == ""


def test_load_quiet_suppresses_output_on_success(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[CheckResult.passed("network", "mcp:s1", "reachable")])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=True)
    out = capsys.readouterr().out
    assert out == ""


def test_load_quiet_still_shows_output_on_failure(capsys: pytest.CaptureFixture) -> None:
    check = CheckResult.critical("network", "mcp:s1", "connection refused")
    report = StartupReport(checks=[check])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
        pytest.raises(SystemExit),
    ):
        _cmd_load(["fake.yaml"], json_output=False, quiet=True)
    out = capsys.readouterr().out
    assert "Load FAILED" in out


# ---------------------------------------------------------------------------
# Multi-file config support
# ---------------------------------------------------------------------------


def test_build_parser_check_multiple_configs() -> None:
    parser = _build_parser()
    args = parser.parse_args(["check", "base.yaml", "agents.yaml"])
    assert args.config == ["base.yaml", "agents.yaml"]


def test_build_parser_load_multiple_configs() -> None:
    parser = _build_parser()
    args = parser.parse_args(["load", "base.yaml", "agents.yaml", "extra.yaml"])
    assert args.config == ["base.yaml", "agents.yaml", "extra.yaml"]


def test_check_multi_file_passes_list_to_load_config() -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config) as mock_lc:
        _cmd_check(["base.yaml", "agents.yaml"], json_output=False, quiet=True)
    mock_lc.assert_called_once_with(["base.yaml", "agents.yaml"])


def test_check_single_file_passes_string_to_load_config() -> None:
    app_config = _mock_app_config()
    with patch("strands_compose.cli.load_config", return_value=app_config) as mock_lc:
        _cmd_check(["single.yaml"], json_output=False, quiet=True)
    mock_lc.assert_called_once_with("single.yaml")


# ---------------------------------------------------------------------------
# check – extra ANSI fields (mcp_servers, session_manager, hooks)
# ---------------------------------------------------------------------------


def test_check_ansi_shows_mcp_servers_when_present(capsys: pytest.CaptureFixture) -> None:
    app_config = _mock_app_config(mcp_servers={"my_server": MagicMock()})
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "mcp servers" in out
    assert "my_server" in out


def test_check_ansi_shows_session_manager_when_present(capsys: pytest.CaptureFixture) -> None:
    sm = MagicMock()
    sm.type = "file"
    app_config = _mock_app_config(session_manager=sm)
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "session" in out
    assert "file" in out


def test_check_ansi_shows_hooks_when_present(capsys: pytest.CaptureFixture) -> None:
    agent_with_hooks = MagicMock(hooks=["hook1", "hook2"])
    app_config = _mock_app_config(agents={"a1": agent_with_hooks})
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=False, quiet=False)
    out = capsys.readouterr().out
    assert "hooks" in out
    assert "2" in out


def test_check_json_contains_version_and_extra_fields(capsys: pytest.CaptureFixture) -> None:
    sm = MagicMock()
    sm.type = "s3"
    agent_with_hooks = MagicMock(hooks=["h1"])
    app_config = _mock_app_config(
        agents={"a1": agent_with_hooks},
        session_manager=sm,
    )
    with patch("strands_compose.cli.load_config", return_value=app_config):
        _cmd_check(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    assert "version" in data
    assert data["session_manager"] == "s3"
    assert data["hooks"] == 1


def test_load_json_contains_version(capsys: pytest.CaptureFixture) -> None:
    report = StartupReport(checks=[CheckResult.passed("network", "mcp:s1", "OK")])
    resolved = _mock_resolved()
    with (
        patch("strands_compose.cli.load", return_value=resolved),
        patch("strands_compose.cli.validate_mcp", new=AsyncMock(return_value=report)),
    ):
        _cmd_load(["fake.yaml"], json_output=True, quiet=False)
    data = json.loads(capsys.readouterr().out)
    assert "version" in data
