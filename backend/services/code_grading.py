"""
Module 9: Code Grading Module
- Compare student code output against expected output
- Assign marks based on correctness, compilation, and partial credit
- Check for common errors
- Save structured grading results
"""
from typing import Dict, List, Optional
from services.code_execution import execute_code


def grade_code_submission(
    code: str,
    language: str,
    test_cases: Optional[List[Dict]] = None,
    max_marks: int = 100,
) -> Dict[str, any]:
    """
    Grade a code submission by running it against test cases.

    test_cases format: [{"input": "5\\n3", "expected_output": "8", "marks": 20}, ...]
    If no test_cases provided, just check compilation + basic execution.
    """
    results = {
        "total_marks": max_marks,
        "marks_awarded": 0,
        "compiles": False,
        "test_results": [],
        "errors": [],
        "summary": "",
    }

    # If no test cases, do basic execution check
    if not test_cases:
        test_cases = [{"input": "", "expected_output": None, "marks": max_marks}]

    marks_per_test = max_marks / len(test_cases) if test_cases else max_marks
    total_awarded = 0

    for i, tc in enumerate(test_cases):
        tc_input = tc.get("input", "")
        expected = tc.get("expected_output")
        tc_marks = tc.get("marks", marks_per_test)

        exec_result = execute_code(code, language, stdin_input=tc_input)

        test_result = {
            "test_case": i + 1,
            "input": tc_input[:200],
            "expected_output": expected[:200] if expected else None,
            "actual_output": exec_result["stdout"].strip()[:200],
            "stderr": exec_result["stderr"][:200] if exec_result["stderr"] else None,
            "passed": False,
            "marks_awarded": 0,
            "timed_out": exec_result["timed_out"],
        }

        if exec_result["timed_out"]:
            results["errors"].append(f"Test {i+1}: Timed out")
            test_result["marks_awarded"] = 0

        elif exec_result["return_code"] != 0:
            results["errors"].append(f"Test {i+1}: Runtime/Compilation error")
            # Partial credit for compilation attempt
            test_result["marks_awarded"] = 0

        elif expected is None:
            # No expected output — just check it runs
            results["compiles"] = True
            test_result["passed"] = True
            test_result["marks_awarded"] = round(tc_marks)
            total_awarded += tc_marks

        else:
            results["compiles"] = True
            actual = exec_result["stdout"].strip()
            expected_clean = expected.strip()

            if actual == expected_clean:
                # Exact match
                test_result["passed"] = True
                test_result["marks_awarded"] = round(tc_marks)
                total_awarded += tc_marks
            elif _normalize(actual) == _normalize(expected_clean):
                # Match after normalization (whitespace differences)
                test_result["passed"] = True
                test_result["marks_awarded"] = round(tc_marks * 0.9)
                total_awarded += tc_marks * 0.9
            else:
                # Partial credit if output contains expected
                if expected_clean in actual or actual in expected_clean:
                    test_result["marks_awarded"] = round(tc_marks * 0.4)
                    total_awarded += tc_marks * 0.4

        results["test_results"].append(test_result)

    results["marks_awarded"] = min(round(total_awarded), max_marks)
    passed = sum(1 for t in results["test_results"] if t["passed"])
    total = len(results["test_results"])
    results["summary"] = f"Passed {passed}/{total} test cases. Score: {results['marks_awarded']}/{max_marks}"

    return results


def _normalize(text: str) -> str:
    """Normalize text for comparison: lowercase, strip whitespace, collapse spaces."""
    import re
    text = text.lower().strip()
    text = re.sub(r"\s+", " ", text)
    return text


def analyze_code_quality(code: str, language: str) -> Dict[str, any]:
    """
    Basic static analysis of code quality.
    Checks for common issues without executing.
    """
    issues = []
    suggestions = []
    lines = code.split("\n")

    # Check code length
    if len(lines) < 3:
        issues.append("Code is very short — may be incomplete")
    if len(lines) > 200:
        suggestions.append("Code is quite long — consider breaking into functions")

    # Python-specific checks
    if language == "python":
        if not any("def " in l for l in lines):
            suggestions.append("Consider using functions for better structure")
        if any("except:" in l and "pass" in lines[i + 1] if i + 1 < len(lines) else False for i, l in enumerate(lines)):
            issues.append("Empty except blocks hide errors")

    # General checks
    has_comments = any(l.strip().startswith(("#", "//", "/*")) for l in lines)
    if not has_comments:
        suggestions.append("Add comments to explain your logic")

    return {
        "issues": issues,
        "suggestions": suggestions,
        "line_count": len(lines),
        "has_comments": has_comments,
    }
