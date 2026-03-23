"""Tests for core.utils — import_from_path, load_module_from_file, cli_errors."""

from __future__ import annotations

import logging

import pytest

from strands_compose.utils import (
    _format_exception,
    cli_errors,
    import_from_path,
    load_module_from_file,
)


class TestImportFromPath:
    def test_valid_import(self):
        result = import_from_path("os.path:join")
        assert result is __import__("os").path.join

    def test_missing_colon_raises_value_error(self):
        with pytest.raises(ValueError, match=r"must be in 'module\.path:ObjectName' format"):
            import_from_path("os.path.join")

    def test_nonexistent_module_raises_import_error(self):
        with pytest.raises(ImportError):
            import_from_path("nonexistent.module:Thing")

    def test_nonexistent_attr_raises_attribute_error(self):
        with pytest.raises(AttributeError):
            import_from_path("os.path:nonexistent_function")


class TestLoadModuleFromFile:
    def test_loads_module_from_file(self, tmp_path):
        py = tmp_path / "sample.py"
        py.write_text("VALUE = 42\n")
        mod = load_module_from_file(py)
        assert mod.VALUE == 42

    def test_file_not_found_raises(self):
        with pytest.raises(FileNotFoundError):
            load_module_from_file("/nonexistent/path.py")

    def test_syntax_error_raises_import_error(self, tmp_path):
        py = tmp_path / "bad.py"
        py.write_text("def broken(\n")
        with pytest.raises(ImportError, match="Failed to load"):
            load_module_from_file(py)

    def test_deterministic_module_name(self, tmp_path):
        py = tmp_path / "mod.py"
        py.write_text("X = 1\n")
        m1 = load_module_from_file(py)
        m2 = load_module_from_file(py)
        assert m1.__name__ == m2.__name__


# ── cli_errors ────────────────────────────────────────────────────────────────


class TestFormatException:
    """Unit tests for the _format_exception helper."""

    def test_builtin_exception_no_module_prefix(self):
        exc = ValueError("bad value")
        assert _format_exception(exc) == "ValueError:\nbad value"

    def test_custom_exception_includes_module(self):
        from strands_compose.exceptions import ConfigurationError

        exc = ConfigurationError("invalid config")
        assert (
            _format_exception(exc)
            == "strands_compose.exceptions.ConfigurationError:\ninvalid config"
        )

    def test_exception_without_message(self):
        exc = RuntimeError()
        assert _format_exception(exc) == "RuntimeError"

    def test_multiline_message_preserved(self):
        msg = "line one\nline two\nline three"
        result = _format_exception(ValueError(msg))
        assert result == f"ValueError:\n{msg}"


class TestCliErrors:
    """Tests for the cli_errors context manager."""

    def test_no_exception_passes_through(self):
        with cli_errors(exit_code=0):
            x = 1 + 1
        assert x == 2

    def test_catches_exception_and_prints(self, capsys):
        with cli_errors(exit_code=0):
            raise ValueError("something went wrong")
        captured = capsys.readouterr()
        assert "ValueError:" in captured.err
        assert "something went wrong" in captured.err

    def test_keyboard_interrupt_not_caught(self):
        with pytest.raises(KeyboardInterrupt):
            with cli_errors(exit_code=0):
                raise KeyboardInterrupt

    def test_system_exit_not_caught(self):
        with pytest.raises(SystemExit):
            with cli_errors(exit_code=0):
                raise SystemExit(0)

    def test_calls_sys_exit_with_code(self):
        with pytest.raises(SystemExit) as exc_info:
            with cli_errors(exit_code=1):
                raise RuntimeError("boom")
        assert exc_info.value.code == 1

    def test_exit_code_zero_suppresses_sys_exit(self, capsys):
        # exit_code=0 means suppress sys.exit — useful for tests
        with cli_errors(exit_code=0):
            raise RuntimeError("boom")
        captured = capsys.readouterr()
        assert "RuntimeError:" in captured.err
        assert "boom" in captured.err

    def test_custom_exception_formatted(self, capsys):
        from strands_compose.exceptions import ConfigurationError

        with cli_errors(exit_code=0):
            raise ConfigurationError("bad yaml")
        captured = capsys.readouterr()
        assert "strands_compose.exceptions.ConfigurationError:" in captured.err
        assert "bad yaml" in captured.err


class TestSuppressTaskExceptions:
    """Tests for _SuppressTaskExceptions log filter."""

    def test_suppresses_task_exception_message(self):
        from strands_compose.utils import _SuppressTaskExceptions

        filt = _SuppressTaskExceptions()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.ERROR,
            pathname="",
            lineno=0,
            msg="Task exception was never retrieved",
            args=(),
            exc_info=None,
        )
        assert filt.filter(record) is False

    def test_passes_unrelated_message(self):
        from strands_compose.utils import _SuppressTaskExceptions

        filt = _SuppressTaskExceptions()
        record = logging.LogRecord(
            name="asyncio",
            level=logging.INFO,
            pathname="",
            lineno=0,
            msg="Some normal message",
            args=(),
            exc_info=None,
        )
        assert filt.filter(record) is True
