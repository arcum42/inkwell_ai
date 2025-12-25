import re

def test_regex():
    pattern = r":::UPDATE\s*(.*?)\s*:::\s*\n(.*?)\s*(?::::END:::|:::END|:::)"
    
    # Case 1: Actual newlines (Expected behavior)
    response_normal = """:::UPDATE test.py:::
def foo():
    print("bar")
:::END:::"""
    
    matches_normal = re.findall(pattern, response_normal, re.DOTALL)
    print("--- Normal Newlines ---")
    for path, content in matches_normal:
        print(f"Path: {path}")
        print(f"Content:\n{content}")
        print(f"Content repr: {repr(content)}")

    # Case 2: Literal \n characters
    response_literal = r""":::UPDATE test.py:::
def foo():\n    print("bar")
:::END:::"""
    
    matches_literal = re.findall(pattern, response_literal, re.DOTALL)
    print("\n--- Literal Newlines ---")
    for path, content in matches_literal:
        print(f"Path: {path}")
        print(f"Content:\n{content}")
        print(f"Content repr: {repr(content)}")

if __name__ == "__main__":
    test_regex()
