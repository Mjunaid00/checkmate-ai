"""
Module 8: Code Execution Module
- Compile and run code in a subprocess with a time limit
- Capture stdout, stderr, and return code
- Support Python, C, C++, Java, JavaScript

NOTE: this is NOT a security sandbox. Student code runs with the same
privileges as the backend process. Only use it on trusted machines.
"""
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, Optional

TIMEOUT_SECONDS = 10  # Max execution time
MAX_OUTPUT_CHARS = 5000  # Truncate long outputs


def execute_code(
    code: str,
    language: str,
    stdin_input: Optional[str] = None,
) -> Dict[str, object]:
    """
    Execute code in a subprocess.
    Returns: {"stdout", "stderr", "return_code", "timed_out", "error"}
    """
    language = (language or "").lower().strip()
    runners = {
        "python": _run_python,
        "java": _run_java,
        "c": _run_c,
        "cpp": _run_cpp,
        "javascript": _run_javascript,
    }

    runner = runners.get(language)
    if not runner:
        return _error_result(f"Unsupported language: {language}")

    try:
        return runner(code, stdin_input)
    except FileNotFoundError as e:
        # Compiler / interpreter not installed on this machine
        return _error_result(f"Toolchain not available: {e}")
    except Exception as e:
        return _error_result(str(e))


def _error_result(message: str) -> Dict[str, object]:
    return {"stdout": "", "stderr": message, "return_code": -1, "timed_out": False, "error": True}


def _run_in_subprocess(cmd: list, stdin_input: Optional[str] = None, cwd: Optional[str] = None) -> Dict:
    """Run a command with timeout and capture output (UTF-8, never crashes on odd bytes)."""
    try:
        result = subprocess.run(
            cmd,
            input=stdin_input,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=TIMEOUT_SECONDS,
            cwd=cwd,
        )
        return {
            "stdout": result.stdout[:MAX_OUTPUT_CHARS],
            "stderr": result.stderr[:MAX_OUTPUT_CHARS],
            "return_code": result.returncode,
            "timed_out": False,
            "error": result.returncode != 0,
        }
    except subprocess.TimeoutExpired:
        return {
            "stdout": "",
            "stderr": f"Execution timed out after {TIMEOUT_SECONDS}s",
            "return_code": -1,
            "timed_out": True,
            "error": True,
        }


def _run_script(code: str, suffix: str, cmd_prefix: list, stdin_input: Optional[str]) -> Dict:
    """
    Write `code` to a temp file, run `cmd_prefix + [file]`, then delete the file.
    The file is CLOSED before running and before unlinking — on Windows an open
    file cannot be deleted, which previously made every run report an error.
    """
    fd, path = tempfile.mkstemp(suffix=suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(code)
        return _run_in_subprocess(cmd_prefix + [path], stdin_input)
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _run_python(code: str, stdin_input: Optional[str] = None) -> Dict:
    # sys.executable = the interpreter running the backend (works even when
    # "python" is not on PATH, e.g. a conda env started directly).
    return _run_script(code, ".py", [sys.executable, "-I"], stdin_input)


def _run_javascript(code: str, stdin_input: Optional[str] = None) -> Dict:
    return _run_script(code, ".js", ["node"], stdin_input)


def _run_c(code: str, stdin_input: Optional[str] = None) -> Dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "main.c"
        exe = Path(tmpdir) / "main.exe"
        src.write_text(code, encoding="utf-8")

        compile_result = _run_in_subprocess(["gcc", str(src), "-o", str(exe)])
        if compile_result["error"]:
            compile_result["stderr"] = "Compilation Error:\n" + compile_result["stderr"]
            return compile_result

        return _run_in_subprocess([str(exe)], stdin_input)


def _run_cpp(code: str, stdin_input: Optional[str] = None) -> Dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        src = Path(tmpdir) / "main.cpp"
        exe = Path(tmpdir) / "main.exe"
        src.write_text(code, encoding="utf-8")

        compile_result = _run_in_subprocess(["g++", str(src), "-o", str(exe)])
        if compile_result["error"]:
            compile_result["stderr"] = "Compilation Error:\n" + compile_result["stderr"]
            return compile_result

        return _run_in_subprocess([str(exe)], stdin_input)


def _run_java(code: str, stdin_input: Optional[str] = None) -> Dict:
    with tempfile.TemporaryDirectory() as tmpdir:
        match = re.search(r"public\s+class\s+(\w+)", code) or re.search(r"class\s+(\w+)", code)
        class_name = match.group(1) if match else "Main"

        src = Path(tmpdir) / f"{class_name}.java"
        src.write_text(code, encoding="utf-8")

        compile_result = _run_in_subprocess(["javac", str(src)], cwd=tmpdir)
        if compile_result["error"]:
            compile_result["stderr"] = "Compilation Error:\n" + compile_result["stderr"]
            return compile_result

        return _run_in_subprocess(["java", "-cp", tmpdir, class_name], stdin_input)
