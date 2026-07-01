"""Every shipped example config loads through the real pipeline with faked runtime.

Guards that the documented examples never rot. Strands is faked only at our
resolver seams (``fake_runtime``); agents, tools, hooks, and orchestrations are
built for real.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from strands_compose.config import ResolvedConfig, load

REPO_ROOT = Path(__file__).resolve().parents[2]
EXAMPLES_DIR = REPO_ROOT / "examples"


def _example_inputs() -> list:
    params = []
    for example_dir in sorted(
        p for p in EXAMPLES_DIR.iterdir() if p.is_dir() and p.name[:2].isdigit()
    ):
        yaml_files = sorted(
            example_dir.glob("*.y*ml"),
            key=lambda path: (path.name != "base.yaml", path.name),
        )
        if not yaml_files:
            continue
        load_input = str(yaml_files[0]) if len(yaml_files) == 1 else [str(p) for p in yaml_files]
        params.append(pytest.param(load_input, id=example_dir.name))
    return params


@pytest.mark.integration
@pytest.mark.parametrize("config_input", _example_inputs())
def test_example_config_loads(config_input, fake_runtime):
    resolved = load(config_input)
    assert isinstance(resolved, ResolvedConfig)
    assert resolved.entry is not None
    resolved.mcp_lifecycle.stop()
