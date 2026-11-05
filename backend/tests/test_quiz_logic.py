"""
Quiz question validation (MCQ + true/false) and the server-side submission window.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _mcq(**over):
    q = {"type": "mcq", "question_text": "2+2?", "options": ["1", "2", "3", "4"], "correct_index": 3, "marks": 2}
    q.update(over)
    return q


def _tf(**over):
    q = {"type": "true_false", "question_text": "The sky is blue.", "options": ["True", "False"], "correct_index": 0, "marks": 1}
    q.update(over)
    return q


# ── validate_questions ───────────────────────────────────────────────────────

def test_validate_accepts_mcq_and_true_false_and_sums_marks():
    from services.quiz_logic import validate_questions
    assert validate_questions([_mcq(), _tf()]) == 3


def test_validate_defaults_missing_type_to_mcq():
    from services.quiz_logic import validate_questions
    q = _mcq()
    del q["type"]
    assert validate_questions([q]) == 2


def test_validate_true_false_needs_exactly_two_options():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError, match="Question 1"):
        validate_questions([_tf(options=["True", "False", "Maybe"])])


def test_validate_true_false_correct_index_must_be_0_or_1():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError):
        validate_questions([_tf(correct_index=2)])


def test_validate_mcq_allows_two_to_six_options():
    from services.quiz_logic import validate_questions, QuizValidationError
    assert validate_questions([_mcq(options=["a", "b", "c"], correct_index=2)]) == 2
    with pytest.raises(QuizValidationError, match="2 to 6 options"):
        validate_questions([_mcq(options=["only one"], correct_index=0)])
    with pytest.raises(QuizValidationError):
        validate_questions([_mcq(options=list("abcdefg"), correct_index=0)])


def test_validate_mcq_correct_index_within_options():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError, match="correct_index"):
        validate_questions([_mcq(correct_index=4)])


def test_validate_rejects_unknown_type_empty_text_and_bad_marks():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError, match="type"):
        validate_questions([_mcq(type="essay")])
    with pytest.raises(QuizValidationError, match="text"):
        validate_questions([_mcq(question_text="   ")])
    with pytest.raises(QuizValidationError, match="marks"):
        validate_questions([_mcq(marks=0)])
    with pytest.raises(QuizValidationError, match="At least one"):
        validate_questions([])


def test_validate_rejects_blank_option_text():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError, match="option"):
        validate_questions([_mcq(options=["a", "", "c", "d"])])


# ── submission_window ────────────────────────────────────────────────────────

def _quiz(limit=30, deadline=None):
    return {"time_limit_minutes": limit, "deadline": deadline}


def test_window_open_within_time_limit():
    from services.quiz_logic import submission_window
    started = datetime(2026, 11, 5, 10, 0, 0)
    w = submission_window(_quiz(30), started, now=started + timedelta(minutes=10))
    assert w["open"] is True
    assert w["ends_at"] == started + timedelta(minutes=30)
    assert w["late_by_seconds"] == 0
    assert w["reason"] is None


def test_window_grace_after_time_limit_is_open_but_late():
    from services.quiz_logic import submission_window
    started = datetime(2026, 11, 5, 10, 0, 0)
    w = submission_window(_quiz(30), started, now=started + timedelta(minutes=30, seconds=45), grace_seconds=120)
    assert w["open"] is True
    assert w["late_by_seconds"] == 45


def test_window_closed_after_grace():
    from services.quiz_logic import submission_window
    started = datetime(2026, 11, 5, 10, 0, 0)
    w = submission_window(_quiz(30), started, now=started + timedelta(minutes=33), grace_seconds=120)
    assert w["open"] is False
    assert w["reason"] == "time_limit"


def test_window_ends_at_deadline_when_deadline_is_sooner():
    from services.quiz_logic import submission_window
    started = datetime(2026, 11, 5, 10, 0, 0)
    deadline = started + timedelta(minutes=5)
    w = submission_window(_quiz(30, deadline), started, now=started + timedelta(minutes=1))
    assert w["ends_at"] == deadline
    assert w["open"] is True


def test_window_closed_after_deadline_plus_grace():
    from services.quiz_logic import submission_window
    started = datetime(2026, 11, 5, 10, 0, 0)
    deadline = started + timedelta(minutes=5)
    w = submission_window(_quiz(30, deadline), started, now=deadline + timedelta(minutes=3), grace_seconds=120)
    assert w["open"] is False
    assert w["reason"] == "deadline"
