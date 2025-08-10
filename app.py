# backend/main.py
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import re
import ast
import io
import contextlib
import textwrap

app = FastAPI(title="Twi DSL API", version="2.0")

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
    (r'\bbɔ mmirika\s+wɔ\s+(.+?)\s+kyekyere\s+(\w+)', r'for \2 in \1:'),
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
    """Simple replacement-based translator (line-oriented)."""
    lines = code.strip().splitlines()
    output = []
    for line in lines:
        original = line
        for pattern, replacement in LEXICON:
            line = re.sub(pattern, replacement, line)
        # preserve indentation heuristics for constructs solved above
        output.append(line)
    return "\n".join(output)


def validate_python(code: str) -> (bool, str):
    try:
        ast.parse(code)
        return True, ""
    except SyntaxError as e:
        return False, str(e)


def safe_check(python_code: str) -> None:
    """Basic safety reject list - extend in production."""
    forbidden = ["import os", "import sys", "__import__", "open(", "subprocess", "socket", "shutil", "os.system"]
    for f in forbidden:
        if f in python_code:
            raise HTTPException(status_code=400, detail=f"Use of '{f}' is forbidden.")


def execute_python(py_code: str) -> dict:
    """Execute code in-process but captured stdout/stderr (prototype only)."""
    # NOTE: For production, replace this with containerized runner.
    safe_check(py_code)
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(out_buf):
            # execute in a restricted globals dict (still not fully secure)
            exec(py_code, {"__builtins__": __builtins__}, {})

    except Exception as e:
        err_buf.write(str(e))
    return {"stdout": out_buf.getvalue(), "stderr": err_buf.getvalue()}


@app.post("/api/translate")
def api_translate(req: TwiCode):
    py_code = twi_to_py(req.twi_code)
    ok, err = validate_python(py_code)
    if not ok:
        return {"ok": False, "error": "syntax_error", "message": err, "python_code": py_code}
    return {"ok": True, "python_code": py_code}


@app.post("/api/run")
def api_run(req: TwiCode):
    py_code = twi_to_py(req.twi_code)
    ok, err = validate_python(py_code)
    if not ok:
        return {"ok": False, "error": "syntax_error", "message": err, "python_code": py_code}
    result = execute_python(py_code)
    return {"ok": True, "python_code": py_code, "stdout": result["stdout"], "stderr": result["stderr"]}
