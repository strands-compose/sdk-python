"""Startup health-check aggregation and the opt-in MCP validator."""

from __future__ import annotations

import pytest

from strands_compose.config.resolvers import ResolvedInfra
from strands_compose.startup.report import CheckResult, StartupError, StartupReport
from strands_compose.startup.validator import validate_mcp


def test_report_ok_when_no_critical_checks():
    report = StartupReport(
        checks=[CheckResult.passed("net", "s", "ok"), CheckResult.warn("net", "s", "slow")]
    )
    assert report.ok
    assert len(report.warnings) == 1


def test_report_not_ok_with_a_critical_check():
    report = StartupReport(checks=[CheckResult.critical("net", "s", "down")])
    assert not report.ok
    assert len(report.critical_checks) == 1


def test_raise_if_critical_raises_startup_error():
    report = StartupReport(checks=[CheckResult.critical("net", "s", "down")])
    with pytest.raises(StartupError):
        report.raise_if_critical()


def test_passed_checks_are_collected():
    report = StartupReport(
        checks=[CheckResult.passed("net", "s", "ok"), CheckResult.critical("net", "t", "bad")]
    )
    assert len(report.passed_checks) == 1


async def test_validate_mcp_on_empty_infra_reports_ok():
    report = await validate_mcp(ResolvedInfra())
    assert report.ok
    assert report.checks == []
