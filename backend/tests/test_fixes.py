"""
Focused regression tests for the 2026-11-04 bug fixes.

Run from backend/:
    python -m pytest tests -q
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ── core.llm JSON extraction + score coercion ───────────────────────────────

def test_extract_json_object_plain():
    from core.llm import extract_json_object
    assert extract_json_object('{"score": 7}') == {"score": 7}


def test_extract_json_object_strips_fences_and_prose():
    from core.llm import extract_json_object
    text = 'Sure, here is the result:\n```json\n{"score": 5, "feedback": "ok"}\n```\nThanks!'
    assert extract_json_object(text) == {"score": 5, "feedback": "ok"}


def test_extract_json_object_raises_on_garbage():
    from core.llm import extract_json_object
    with pytest.raises(ValueError):
        extract_json_object("no json here")


@pytest.mark.parametrize(
    "raw, max_marks, expected",
    [
        (7, 10, 7),
        ("8", 10, 8),
        ("7.6", 10, 8),
        (12, 10, 10),      # clamp high
        (-3, 10, 0),       # clamp low
        ("n/a", 10, 0),    # unparsable -> 0
        (None, 10, 0),
    ],
)
def test_coerce_score(raw, max_marks, expected):
    from core.llm import coerce_score
    assert coerce_score(raw, max_marks) == expected


# ── services.code_execution on Windows ───────────────────────────────────────

def test_run_python_returns_stdout_and_cleans_temp_file():
    """On Windows the old code unlinked the temp file while it was still open
    (PermissionError) so every Python run reported an error."""
    from services.code_execution import execute_code
    result = execute_code("print('hello ünïcode')", "python")
    assert result["error"] is False, result
    assert result["return_code"] == 0
    assert "hello" in result["stdout"]


def test_run_python_reports_runtime_error():
    from services.code_execution import execute_code
    result = execute_code("raise SystemExit(3)", "python")
    assert result["error"] is True
    assert result["return_code"] == 3


# ── services.ocr backend selection ──────────────────────────────────────────

def test_ocr_backend_none_returns_empty(monkeypatch, tmp_path):
    import services.ocr as ocr
    monkeypatch.setattr(ocr, "OCR_BACKEND", "none")
    f = tmp_path / "x.png"
    f.write_bytes(b"")
    assert ocr.extract_text(f) == ""
    assert ocr.extract_text_from_first_page(f) == ""


def test_ocr_unknown_suffix_returns_empty():
    import services.ocr as ocr
    assert ocr.extract_text(Path("answer.docx")) == ""


# ── routers.dashboard stats scoping (pure helper) ───────────────────────────

def test_dashboard_stats_from_submissions_helper():
    from routers.dashboard import summarize_submissions
    subs = [
        {"status": "graded", "score": 8, "total_marks": 10},
        {"status": "graded", "score": 6, "total_marks": 10},
        {"status": "processing", "score": None, "total_marks": 10},
        {"status": "failed", "total_marks": 10},
    ]
    stats = summarize_submissions(subs)
    assert stats == {"total_exams": 4, "graded_exams": 2, "average_percentage": 70.0}


def test_dashboard_stats_empty():
    from routers.dashboard import summarize_submissions
    assert summarize_submissions([]) == {"total_exams": 0, "graded_exams": 0, "average_percentage": 0.0}


# ── deadline parsing (timezone-aware → naive UTC) ───────────────────────────

@pytest.mark.parametrize(
    "raw, expected_iso",
    [
        ("2030-01-01T10:00:00Z", "2030-01-01T10:00:00"),
        ("2030-01-01T10:00:00+09:00", "2030-01-01T01:00:00"),
        ("2030-01-01T10:00", "2030-01-01T10:00:00"),   # naive: treated as UTC
    ],
)
def test_parse_deadline_to_utc(raw, expected_iso):
    from core.timeutil import parse_deadline
    assert parse_deadline(raw).isoformat() == expected_iso


def test_parse_deadline_rejects_garbage():
    from core.timeutil import parse_deadline
    with pytest.raises(ValueError):
        parse_deadline("next tuesday")
