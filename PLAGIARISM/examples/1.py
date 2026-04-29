def calculator(a, b, operator):
    if operator == '+':
        return a + b
    elif operator == '-':
        return a - b
    elif operator == '*':
        return a * b
    elif operator == '/':
        return a / b if b != 0 else "Cannot divide by zero"
    else:
        return "Invalid operator"

print(calculator(10, 5, '+'))  # Output: 15
