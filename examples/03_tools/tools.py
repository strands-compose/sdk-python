"""Text analysis tools for the 03_tools example.

Functions must be decorated with ``@tool`` from strands so that
strands-compose can discover and register them with the agent.
"""

from strands.tools.decorator import tool


@tool
def count_words(text: str) -> int:
    """Count the number of words in the given text."""
    return len(text.split())


@tool
def count_characters(text: str) -> int:
    """Count characters in the given text, excluding spaces."""
    return len(text.replace(" ", ""))


@tool
def extract_sentences(text: str) -> list[str]:
    """Split text into individual sentences.

    Args:
        text: The text to split into sentences.

    Returns:
        A list of sentence strings with leading/trailing whitespace removed.
    """
    import re

    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s for s in sentences if s]


@tool
def reverse_words(text: str) -> str:
    """Return the text with the word order reversed.

    Args:
        text: The text whose words will be reversed.

    Returns:
        A new string with the same words in reverse order.
    """
    return " ".join(reversed(text.split()))
