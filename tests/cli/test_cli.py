"""CLI behaviour through the public main() entry point.

Asserts on exit behaviour and JSON payload shape (a real CLI contract), never
on ANSI prose.
"""

from __future__ import annotations

import json

import pytest

from strands_compose.cli import main
from tests.factories import write_config


def _run(argv, monkeypatch):
    monkeypatch.setattr("sys.argv", ["strands-compose", *argv])
    main()


def test_check_valid_config_exits_zero(tmp_path, monkeypatch):
    cfg = write_config(tmp_path, "agents:\n  a:\n    system_prompt: hi\nentry: a")
    _run(["check", str(cfg), "--quiet"], monkeypatch)  # returns normally = exit 0


def test_check_invalid_config_exits_nonzero(tmp_path, monkeypatch):
    cfg = write_config(tmp_path, "agents:\n  a:\n    system_prompt: hi\nentry: ghost")
    with pytest.raises(SystemExit) as exc:
        _run(["check", str(cfg)], monkeypatch)
    assert exc.value.code == 1


def test_check_json_output_reports_entry_and_agents(tmp_path, monkeypatch, capsys):
    cfg = write_config(tmp_path, "agents:\n  a:\n    system_prompt: hi\nentry: a")
    _run(["check", str(cfg), "--json"], monkeypatch)

    payload = json.loads(capsys.readouterr().out)
    assert payload["ok"] is True
    assert payload["entry"] == "a"
    assert payload["agents"] == ["a"]


def test_load_minimal_config_exits_zero(tmp_path, monkeypatch):
    # No MCP servers configured → validate_mcp does no network probing.
    cfg = write_config(tmp_path, "agents:\n  a:\n    system_prompt: hi\nentry: a")
    _run(["load", str(cfg), "--quiet"], monkeypatch)


def test_missing_subcommand_errors(monkeypatch):
    with pytest.raises(SystemExit):
        _run([], monkeypatch)
