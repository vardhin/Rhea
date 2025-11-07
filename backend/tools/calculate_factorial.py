# filepath: /home/vardhin/Documents/git/Rhea/backend/tools/calculate_factorial.py
from tool_server import tool

@tool(name="calculate_factorial", category="math", tags=["factorial", "number", "calculation"])
def calculate_factorial(number: int) -> int:
    """Calculates the factorial of a non-negative integer.

    Args:
        number (int): The non-negative integer for which to calculate the factorial.

    Returns:
        int: The factorial of the given number.

    Raises:
        ValueError: If the input number is negative.
        TypeError: If the input is not an integer.
    """
    if not isinstance(number, int):
        raise TypeError("Input must be an integer.")
    if number < 0:
        raise ValueError("Factorial is not defined for negative numbers.")
    
    result = 1
    for i in range(1, number + 1):
        result *= i
    return result