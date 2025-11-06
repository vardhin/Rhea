from tool_server import tool

@tool(name="uppercase", category="text", tags=["string", "formatting"])
def convert_uppercase(text: str) -> str:
    """Convert text to uppercase"""
    return text.upper()

@tool(name="word_count", category="text", tags=["string", "analysis"])
def count_words(text: str) -> dict:
    """Count words in text"""
    words = text.split()
    return {
        'word_count': len(words),
        'character_count': len(text),
        'unique_words': len(set(words))
    }

@tool(name="reverse_text", category="text", tags=["string", "formatting"])
def reverse_text(text: str) -> str:
    """Reverse the given text"""
    return text[::-1]