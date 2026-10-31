"""Edge condition functions for the 13_graph_conditions example.

Each function receives the graph's ``GraphState`` and returns True/False to
decide whether the edge should fire.
"""

from __future__ import annotations

from strands.multiagent.graph import GraphState


def needs_revision(state: GraphState) -> bool:
    """Route back to writer if the reviewer says REVISE.

    Args:
        state: Graph state holding each finished node's result.

    Returns:
        True if the content needs revision.
    """
    return "REVISE" in str(state.results["reviewer"].result).upper()


def is_approved(state: GraphState) -> bool:
    """Route to publisher if the reviewer says APPROVED.

    Args:
        state: Graph state holding each finished node's result.

    Returns:
        True if the content is approved for publishing.
    """
    return "APPROVED" in str(state.results["reviewer"].result).upper()
