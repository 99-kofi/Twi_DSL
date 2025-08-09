"""
Initial implementation for Twi DSL Playground — prototype single-file server + parser + runner.

Files implemented in this prototype (single module for quick iteration):
- Parser: deterministic line-based parser that converts Twi DSL -> Python AST/text
- Emitter: builds Python source using ast where possible
- FastAPI app: /translate and /execute endpoints
- Runner: executes translated Python in a separate subprocess with resource/time limits

NOTES / TODOs (next steps):
- Replace subprocess runner with container-based sandbox (Docker or Firecracker) for production
- Harden parser to emit AST directly and strictly whitelist constructs
- Add storage, session handling, Streamlit frontend integration
- Add tests and CI

Run this file as a module (python twi-dsl-initial-implementation.py) to start the FastAPI server.

"""

import re
import ast
import astor
import tempfile
import subprocess
import shlex
import os
import sys
import json
import textwrap
import time
from typing import List, Dict, Any, Tuple
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from multiprocessing import Process, Queue

# ---------------------- Parser ----------------------
# This is a deterministic line-based parser prototype.
# It translates Twi DSL lines into Python source lines while tracking
# indentation and producing a mapping from Twi line -> Python line.

class TranslationResult(BaseModel):
    python_code: str
    mapping: List[Dict[str, Any]]  # list of {twi_line_no, py_line_no}

class TwiParser:
    KEYWORDS = {
        "nokware": "True",
        "atɔkyɛ": "False",
        "ka ho": "+",
    }

    def __init__(self):
        pass

    def translate(self, twi_code: str) -> TranslationResult:
        lines = twi_code.strip().splitlines()
        py_lines: List[str] = []
        mapping: List[Dict[str, int]] = []
        indent_level = 0

        for i, raw in enumerate(lines, start=1):
            line = raw.strip()
            if not line:
                py_lines.append("")
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                continue

            # assignment: siesie x = 5
            if line.startswith("siesie "):
                rest = line.replace("siesie ", "", 1)
                py_line = ("    " * indent_level) + rest
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                continue

            # print: ka "Hello"
            m = re.match(r'^ka\s+"([^"]*)"$', line)
            if m:
                msg = m.group(1)
                py_line = ("    " * indent_level) + f'print("{msg}")'
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                continue

            # show variable: sɔ hwɛ x
            if line.startswith("sɔ hwɛ "):
                var = line.replace("sɔ hwɛ ", "", 1)
                py_line = ("    " * indent_level) + f"print({var})"
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                continue

            # if: sɛ x > 3 a
            if line.startswith("sɛ ") and line.endswith(" a"):
                cond = line[2:-2].strip()
                py_line = ("    " * indent_level) + f"if {cond}:"
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                indent_level += 1
                continue

            # else: nanso
            if line == "nanso":
                # lower one indent and insert else:
                indent_level = max(indent_level - 1, 0)
                py_line = ("    " * indent_level) + "else:"
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                indent_level += 1
                continue

            # indent hint: kyerɛ me -> increase indent level for next lines
            if line == "kyerɛ me":
                indent_level += 1
                # no direct output, but add a comment line to help mapping
                py_lines.append(("    " * (indent_level-1)) + "# kyerɛ me (indent)")
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                continue

            # for loop: bɔ mmirika wɔ range(5) kyekyere i
            m = re.match(r"bɔ mmirika wɔ (.+) kyekyere (\w+)", line)
            if m:
                iterable = m.group(1).strip()
                var = m.group(2).strip()
                py_line = ("    " * indent_level) + f"for {var} in {iterable}:"
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                indent_level += 1
                continue

            # function def: yɛ adwuma my_func():
            if line.startswith("yɛ adwuma "):
                func = line.replace("yɛ adwuma ", "", 1)
                if not func.endswith(":"):
                    func = func + ":"
                py_line = ("    " * indent_level) + f"def {func}"
                py_lines.append(py_line)
                mapping.append({"twi_line": i, "py_line": len(py_lines)})
                indent_level += 1
                continue

            # fallback: replace keywords and emit
            safe_line = line
            for twi_kw, py_kw in self.KEYWORDS.items():
                safe_line = safe_line.replace(twi_kw, py_kw)
            py_line = ("    " * indent_level) + safe_line
            py_lines.append(py_line)
            mapping.append({"twi_line": i, "py_line": len(py_lines)})

        python_code = "\n".join(py_lines)
        return TranslationResult(python_code=python_code, mapping=mapping)

# ---------------------- Emitter / Validator ----------------------
# We will attempt to parse the emitted python_code to ensure it's syntactically valid.
# For now we rely on ast.parse; later we want to build AST directly.

class Emitter:
    @staticmethod
    def validate(python_code: str) -> Tuple[bool, str]:
        try:
            ast.parse(python_code)
            return True, ""
        except SyntaxError as e:
            return False, str(e)

# ---------------------- Runner (Subprocess-based sandbox prototype) ----------------------
# This is a simple isolated runner that executes code in a separate python process
# with a timeout. It is NOT production-secure but suffices for early development.

RUN_TIMEOUT = 4  # seconds
MAX_OUTPUT_BYTES = 20000

def run_code_subprocess(python_code: str, timeout: int = RUN_TIMEOUT) -> Dict[str, Any]:
    # write code to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False) as f:
        f.write(python_code)
        fname = f.name

    # Use sys.executable to run a new interpreter
    cmd = [sys.executable, fname]

    try:
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            out, err = proc.communicate(timeout=timeout)
        except subprocess.TimeoutExpired:
            proc.kill()
            out, err = proc.communicate()
            return {
                "stdout": out.decode(errors='ignore')[:MAX_OUTPUT_BYTES],
                "stderr": err.decode(errors='ignore')[:MAX_OUTPUT_BYTES],
                "timeout": True,
                "exit_code": proc.returncode,
            }

        return {
            "stdout": out.decode(errors='ignore')[:MAX_OUTPUT_BYTES],
            "stderr": err.decode(errors='ignore')[:MAX_OUTPUT_BYTES],
            "timeout": False,
            "exit_code": proc.returncode,
        }
    finally:
        try:
            os.remove(fname)
        except Exception:
            pass

# ---------------------- FastAPI Endpoints ----------------------

app = FastAPI(title="Twi DSL API (prototype)")

class TranslateRequest(BaseModel):
    twi_code: str

class ExecuteRequest(BaseModel):
    twi_code: str = None
    python_code: str = None
    timeout: int = RUN_TIMEOUT

@app.post('/api/translate', response_model=TranslationResult)
def api_translate(req: TranslateRequest):
    parser = TwiParser()
    res = parser.translate(req.twi_code)
    # validate
    ok, err = Emitter.validate(res.python_code)
    if not ok:
        # return partial translation with error info via HTTPError
        raise HTTPException(status_code=400, detail={"error": "syntax", "message": err, "python_code": res.python_code})
    return res

@app.post('/api/execute')
def api_execute(req: ExecuteRequest):
    if req.python_code is None and req.twi_code is None:
        raise HTTPException(status_code=400, detail="Provide twi_code or python_code")

    parser = TwiParser()
    if req.python_code is None:
        translated = parser.translate(req.twi_code)
        python_code = translated.python_code
    else:
        python_code = req.python_code
        translated = None

    # Validate syntactically before running
    ok, err = Emitter.validate(python_code)
    if not ok:
        raise HTTPException(status_code=400, detail={"error": "syntax", "message": err, "python_code": python_code})

    # Simple safety check: disallow certain substrings (very naive)
    forbidden = ['import os', 'import sys', '__import__', 'open(', 'subprocess', 'socket', 'shutil', 'os.system']
    for f in forbidden:
        if f in python_code:
            raise HTTPException(status_code=400, detail={"error": "forbidden", "message": f"Use of '{f}' is not allowed"})

    result = run_code_subprocess(python_code, timeout=req.timeout)
    response = {
        "stdout": result['stdout'],
        "stderr": result['stderr'],
        "timeout": result['timeout'],
        "exit_code": result['exit_code'],
    }
    if translated is not None:
        response['python_code'] = translated.python_code
        response['mapping'] = translated.mapping
    return response

# ---------------------- Dev server entrypoint ----------------------
if __name__ == '__main__':
    import uvicorn
    print("Starting Twi DSL prototype API on http://127.0.0.1:8000")
    uvicorn.run(app, host='127.0.0.1', port=8000, log_level='info')
