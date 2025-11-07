from tool_server import tool

@tool(name="multiply", category="math", tags=["multiplication", "arithmetic", "calculation"])
def multiply(number1: float, number2: float) -> float:
    """Multiplies two numbers together and returns the product."""
    return number1 * number2