"""The single deliberate contract snapshot for the public event/manifest shape.

Guards the ``StreamEvent`` protocol vocabulary and the ``SessionManifest`` field
shape against accidental drift. A diff here is a *reviewed decision* — regenerate
the baseline with ``python -m tests.contract.test_shape`` only for intended changes.

This is the one sanctioned snapshot; do not add others.
"""

from __future__ import annotations

import dataclasses
import json
from pathlib import Path

from pydantic import BaseModel

from strands_compose import types

BASELINE = Path(__file__).parent / "shape_baseline.json"


def _model_fields(model: type[BaseModel]) -> list[str]:
    return sorted(model.model_fields)


def public_shape() -> dict[str, object]:
    """Compute the observable event/manifest shape consumers depend on."""
    return {
        "event_types": sorted(e.value for e in types.EventType),
        "stream_event_fields": sorted(f.name for f in dataclasses.fields(types.StreamEvent)),
        "session_manifest": _model_fields(types.SessionManifest),
        "agent_descriptor": _model_fields(types.AgentDescriptor),
        "orchestration_descriptor": _model_fields(types.OrchestrationDescriptor),
        "entry_descriptor": _model_fields(types.EntryDescriptor),
        "model_descriptor": _model_fields(types.ModelDescriptor),
        "node_ref": _model_fields(types.NodeRef),
        "edge_ref": _model_fields(types.EdgeRef),
    }


def test_public_shape_matches_reviewed_baseline():
    expected = json.loads(BASELINE.read_text())
    assert public_shape() == expected


if __name__ == "__main__":  # regenerate the baseline (reviewed change only)
    BASELINE.write_text(json.dumps(public_shape(), indent=2, sort_keys=True) + "\n")
    print(f"wrote {BASELINE}")  # noqa: T201
