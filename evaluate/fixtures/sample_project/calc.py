def add_numbers(a: int, b: int) -> int:
    return a + b


def multiply_numbers(a: int, b: int) -> int:
    result = 0
    for _ in range(abs(b)):
        result += a
    return result if b >= 0 else -result
