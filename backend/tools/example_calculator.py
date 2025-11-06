from tool_server import tool

@tool(name="add", category="math", tags=["calculator", "arithmetic"])
def add_numbers(a: float, b: float) -> float:
    """Add two numbers together"""
    return a + b

@tool(name="multiply", category="math", tags=["calculator", "arithmetic"])
def multiply_numbers(a: float, b: float) -> float:
    """Multiply two numbers"""
    return a * b

@tool(name="calculate", category="math", tags=["calculator", "advanced"])
def calculate_expression(expression: str) -> float:
    """
    Safely evaluate a mathematical expression
    Example: "2 + 2 * 3"
    """
    try:
        # Only allow safe operations
        allowed_chars = set("0123456789+-*/()%. ")
        if not all(c in allowed_chars for c in expression):
            raise ValueError("Invalid characters in expression")
        
        result = eval(expression)
        return result
    except Exception as e:
        raise ValueError(f"Failed to evaluate expression: {str(e)}")