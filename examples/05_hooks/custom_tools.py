"""Mock research tools for the 05_hooks example.

These return deterministic mock data so the example works without
any real external API keys. The agent can call them multiple times
to trigger MaxToolCallsGuard.
"""

from strands.tools.decorator import tool


@tool
def search(query: str) -> str:
    """Search the web for information about a topic.

    Args:
        query: The search query string.

    Returns:
        A string of mock search results.
    """
    snippets = [
        f"Study shows {query} has significant measurable impact on outcomes.",
        f"Recent analysis of {query} reveals three key trends for 2025.",
        f"Experts debate best practices around {query} — consensus emerging.",
        f"New data on {query} contradicts earlier assumptions from 2020.",
    ]
    # Pick two snippets at a query-derived index so different queries return different results.
    idx = sum(query.encode()) % len(snippets)
    picked = [snippets[idx], snippets[(idx + 1) % len(snippets)]]
    return f"[Search: {query!r}]\n" + "\n".join(picked)


@tool
def get_facts(topic: str) -> str:
    """Retrieve key facts about a topic.

    Args:
        topic: The topic to retrieve facts for.

    Returns:
        A string listing mock facts about the topic.
    """
    return (
        f"[Facts: {topic!r}]\n"
        f"• Fact 1: {topic} was first studied in the early 20th century.\n"
        f"• Fact 2: Over 1,000 peer-reviewed papers mention {topic} annually.\n"
        f"• Fact 3: Industries most affected by {topic} spend $2B+ on research.\n"
        f"• Fact 4: Public awareness of {topic} increased 40% since 2020.\n"
        f"• Fact 5: Three countries lead global investment in {topic} research."
    )
