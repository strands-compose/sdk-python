"""Pydantic schema for the 16_structured_output example.

The triage agent fills a ``Ticket`` on every call. Field descriptions are part
of the schema the model sees, so they tell it what to put in each field.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class Ticket(BaseModel):
    """A triaged customer support message."""

    category: Literal["billing", "bug", "feature_request", "other"] = Field(
        description="What the message is about."
    )
    priority: Literal["low", "medium", "high"] = Field(
        description="high when the customer is blocked or losing money."
    )
    summary: str = Field(description="One sentence that states the problem.")
    needs_human: bool = Field(description="True when a person must follow up.")
