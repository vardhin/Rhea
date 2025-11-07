from tool_server import tool

@tool(name="count_char_in_string", category="string_manipulation", tags=["text", "count", "character"])
def count_char_in_string(text: str, char_to_count: str) -> int:
    """Counts the occurrences of a specified character within a given string."""
    return text.count(char_to_count)