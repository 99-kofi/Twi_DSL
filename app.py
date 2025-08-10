from fastapi import FastAPI
from pydantic import BaseModel
import re
import ast
import io
import contextlib

app = FastAPI(title="Twi DSL API", version="2.0")

# Expanded Twi → Python rules
LEXICON = [
    # Assignments & printing
    (r'\bsiesie\s+(\w+)\s*=\s*(.+)', r'\1 = \2'),
    (r'\bka\s+"([^"]*)"', r'print("\1")'),
    (r'\bsɔ hwɛ\s+(\w+)', r'print(\1)'),

    # Conditionals
    (r'\bsɛ\s+(.+?)\s+a\b', r'if \1:'),
    (r'\bna\b', ''),
    (r'\bkyerɛ me\b', '    '),
    (r'\bnanso\b', 'else:'),

    # Loops
    (r'\bbɔ mmirika\b', 'for'),
    (r'\bkyekyere\s+(\w+)', r'\1 in'),
    (r'\bfa so\b', 'while'),

    # Functions
    (r'\byɛ adwuma\b', 'def'),
    (r'\bhyɛ adwuma\b', 'def'),
    (r'\bfrɛ\b', ''),

    # Booleans
    (r'\bnokware\b', 'True'),
    (r'\batɔkyɛ\b', 'False'),

    # Math
    (r'\bka ho\b', '+'),
    (r'\bte ho\b', '-'),
    (r'\bhyɛ ho\b', '*'),
    (r'\bkyekyɛ\b', '/'),

    # Comparisons
    (r'\bkyɛn\b', '>'),
    (r'\bsen\b', '<'),
    (r'\bpɔ\b', '=='),
    (r'\bnnyɛ\b', '!='),

    # Logical operators
    (r'\bnna\b', 'and'),
    (r'\bnana\b', 'or'),
    (r'\bnkyerɛ\b', 'not'),

    # Lists
    (r'\bkyɛfa\b', '['),
    (r'\bto so\b', ']'),

    # Imports
    (r'\bwɔ\s+(\w+)', r'import \1'),
]


class TwiCode(BaseModel):
    twi_code: str


def twi_to_py(code: str) -> str:
    lines = code.strip().split("\n")
    output = []
    for line in lines:
        for pattern, replacement in LEXICON:
            line = re.sub(pattern, replacement, line)
        output.append(line)
    return "\n".join(output)


def is_valid_python(code: str) -> bool:
    try:
        ast.parse(code)
        return True
    except SyntaxError:
        return False


def execute_code(py_code: str) -> str:
    output = io.StringIO()
    try:
        with contextlib.redirect_stdout(output):
            exec(py_code, {}, {})
    except Exception as e:
        return f"[Error]: {str(e)}"
    return output.getvalue()


@app.post("/api/translate")
def translate_code(data: TwiCode):
    py_code = twi_to_py(data.twi_code)
    if not is_valid_python(py_code):
        return {"error": "Invalid Python syntax", "python_code": py_code}
    return {"python_code": py_code}


@app.post("/api/run")
def run_code(data: TwiCode):
    py_code = twi_to_py(data.twi_code)
    if not is_valid_python(py_code):
        return {"error": "Invalid Python syntax", "python_code": py_code}
    result = execute_code(py_code)
    return {"python_code": py_code, "output": result}
