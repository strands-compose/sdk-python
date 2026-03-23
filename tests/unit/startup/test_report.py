"""Tests for core.startup.report — CheckResult, StartupReport."""

from __future__ import annotations

import pytest

from strands_compose.startup.report import CheckResult, StartupError, StartupReport


class TestCheckResult:
    def test_passed_factory(self):
        r = CheckResult.passed("network", "mcp:pg", "Connected")
        assert r.ok is True
        assert r.severity == "info"

    def test_warn_factory(self):
        r = CheckResult.warn("runtime", "model", "Slow", hint="Check latency")
        assert r.ok is False
        assert r.severity == "warning"
        assert r.hint == "Check latency"

    def test_critical_factory(self):
        r = CheckResult.critical("network", "mcp:pg", "Unreachable")
        assert r.ok is False
        assert r.severity == "critical"

    def test_str_passed(self):
        r = CheckResult.passed("network", "mcp:pg", "OK")
        assert "✓" in str(r)

    def test_str_critical(self):
        r = CheckResult.critical("network", "mcp:pg", "Fail", hint="Fix it")
        s = str(r)
        assert "✗" in s
        assert "Fix it" in s


class TestStartupReport:
    def test_ok_when_no_critical(self):
        report = StartupReport(checks=[CheckResult.passed("net", "s", "ok")])
        assert report.ok

    def test_not_ok_when_critical(self):
        report = StartupReport(checks=[CheckResult.critical("net", "s", "bad")])
        assert not report.ok

    def test_raise_if_critical(self):
        report = StartupReport(checks=[CheckResult.critical("net", "s", "boom")])
        with pytest.raises(StartupError):
            report.raise_if_critical()

    def test_no_raise_when_ok(self):
        report = StartupReport(checks=[CheckResult.passed("net", "s", "ok")])
        report.raise_if_critical()  # should not raise

    def test_warnings_property(self):
        report = StartupReport(
            checks=[
                CheckResult.passed("net", "a", "ok"),
                CheckResult.warn("net", "b", "slow"),
            ]
        )
        assert len(report.warnings) == 1

    def test_critical_checks_property(self):
        report = StartupReport(
            checks=[
                CheckResult.passed("net", "a", "ok"),
                CheckResult.critical("net", "b", "fail"),
            ]
        )
        assert len(report.critical_checks) == 1

    def test_passed_checks_property(self):
        report = StartupReport(
            checks=[
                CheckResult.passed("net", "a", "ok"),
                CheckResult.critical("net", "b", "fail"),
            ]
        )
        assert len(report.passed_checks) == 1

    def test_print_summary(self):
        report = StartupReport(
            checks=[
                CheckResult.passed("net", "a", "ok"),
                CheckResult.warn("net", "b", "slow"),
            ]
        )
        report.print_summary()  # should not raise

    def test_print_summary_verbose(self):
        report = StartupReport(checks=[CheckResult.passed("net", "a", "ok")])
        report.print_summary(verbose=True)  # should not raise


class TestStartupError:
    def test_message_format(self):
        report = StartupReport(checks=[CheckResult.critical("net", "s", "boom")])
        err = StartupError(report)
        assert "boom" in str(err)
        assert err.report is report
