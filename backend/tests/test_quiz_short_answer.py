"""
Short-answer questions: validation, answer normalisation, grading and submitted-answer typing.
"""
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def _sa(**over):
    q = {"type": "short_answer", "question_text": "Capital of France?", "accepted_answers": ["Paris"], "marks": 2}
    q.update(over)
    return q


def test_validate_accepts_short_answer_without_options():
    from services.quiz_logic import validate_questions
    assert validate_questions([_sa()]) == 2


def test_validate_short_answer_needs_an_accepted_answer():
    from services.quiz_logic import validate_questions, QuizValidationError
    with pytest.raises(QuizValidationError, match="accepted answer"):
        validate_questions([_sa(accepted_answers=[])])
    with pytest.raises(QuizValidationError, match="accepted answer"):
        validate_questions([_sa(accepted_answers=["  "])])


def test_normalise_short_answer_strips_dedupes_and_clears_options():
    from services.quiz_logic import normalise_question
    q = normalise_question(_sa(accepted_answers=[" Paris ", "paris", "PARIS", "Paris, France"], options=["a", "b"], correct_index=1))
    assert q["accepted_answers"] == ["Paris", "Paris, France"]
    assert q["options"] == [] and q["correct_index"] is None


def test_normalize_answer_ignores_case_punctuation_and_spacing():
    from services.quiz_logic import normalize_answer
    assert normalize_answer("  Paris!  ") == "paris"
    assert normalize_answer("New   York, USA.") == "new york usa"
    assert normalize_answer(None) == ""


@pytest.mark.parametrize("answer, expected", [
    ("paris", True), ("  PARIS. ", True), ("Paris, France", True), ("Lyon", False), ("", False), (-1, False), (None, False),
])
def test_is_correct_short_answer(answer, expected):
    from services.quiz_logic import is_correct
    assert is_correct(_sa(accepted_answers=["Paris", "Paris, France"]), answer) is expected


def test_is_correct_mcq_and_true_false_unchanged():
    from services.quiz_logic import is_correct
    mcq = {"type": "mcq", "options": ["a", "b", "c", "d"], "correct_index": 2}
    assert is_correct(mcq, 2) and not is_correct(mcq, 1) and not is_correct(mcq, "2") and not is_correct(mcq, -1)
    tf = {"type": "true_false", "options": ["True", "False"], "correct_index": 1}
    assert is_correct(tf, 1) and not is_correct(tf, 0)


def test_coerce_answers_types_per_question():
    from services.quiz_logic import coerce_answers
    questions = [{"type": "mcq", "options": ["a", "b", "c", "d"], "correct_index": 0}, _sa(), {"type": "true_false", "options": ["True", "False"], "correct_index": 0}]
    assert coerce_answers(questions, [1, "  Paris ", -1]) == [1, "Paris", -1]
    assert coerce_answers(questions, [-1, "", 0]) == [-1, "", 0]


def test_coerce_answers_rejects_wrong_length_and_types():
    from services.quiz_logic import coerce_answers, QuizValidationError
    questions = [{"type": "mcq", "options": ["a", "b"], "correct_index": 0}, _sa()]
    with pytest.raises(QuizValidationError, match="Expected 2 answers"):
        coerce_answers(questions, [0])
    with pytest.raises(QuizValidationError, match="Question 1"):
        coerce_answers(questions, ["b", "Paris"])
    with pytest.raises(QuizValidationError, match="Question 2"):
        coerce_answers(questions, [0, 3])
    with pytest.raises(QuizValidationError, match="Question 1"):
        coerce_answers(questions, [7, "Paris"])  # option index out of range


def test_weak_questions_counts_short_answers_through_is_correct():
    from services.analytics_helpers import weak_questions
    quizzes = [{"_id": "q", "title": "Q", "questions": [_sa(accepted_answers=["Paris"]), {"type": "mcq", "options": ["a", "b"], "correct_index": 1}]}]
    attempts = [{"quiz_id": "q", "answers": ["paris", 0]}, {"quiz_id": "q", "answers": ["Rome", 1]}]
    out = weak_questions(quizzes, attempts, limit=5)
    assert {(w["question_index"], w["correct_rate"]) for w in out} == {(0, 50.0), (1, 50.0)}
