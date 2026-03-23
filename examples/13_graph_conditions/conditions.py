"""Edge condition functions for the 13_graph_conditions example.

Each function receives the graph's execution context dict and returns
True/False to decide whether the edge should fire.
"""

from __future__ import annotations


def needs_revision(context: dict) -> bool:
    """Route back to writer if the reviewer says REVISE.

    Args:
        context: Graph execution context with last_output from the reviewer.

    Returns:
        True if the content needs revision.
    """
    last_output = str(context.get("last_output", ""))
    return "REVISE" in last_output.upper()


def is_approved(context: dict) -> bool:
    """Route to publisher if the reviewer says APPROVED.

    Args:
        context: Graph execution context with last_output from the reviewer.

    Returns:
        True if the content is approved for publishing.
    """
    last_output = str(context.get("last_output", ""))
    return "APPROVED" in last_output.upper()
