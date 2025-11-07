from tool_server import tool

@tool(name="character_count", category="text", tags=["string", "analysis", "count"])
def character_count(character: str, text: str) -> int:
    """Counts the occurrences of a specific character in a given text.

    Args:
        character: The character to count.
        text: The text in which to count the character.

    Returns:
        The number of times the character appears in the text.
    """
    if not character or len(character) != 1:
        raise ValueError("Character to count must be a single character string.")
    return text.count(character)