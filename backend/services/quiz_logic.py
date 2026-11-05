"""
Pure quiz rules shared by the quizzes router (no database, no FastAPI):

* validate_questions  - MCQ (2-6 options) and true/false (exactly True / False) questions
* submission_window   - when an attempt must be in by, from the SERVER-side start time,
                        the quiz time limit and the deadline (whichever comes first)
"""
from datetime import datetime, timedelta
from typing import Any, Dict, List

QUESTION_TYPES = ("mcq", "true_false")
TRUE_FALSE_OPTIONS = ["True", "False"]
DEFAULT_GRACE_SECONDS = 120  # network / clock slack before a late submission is refused


class QuizValidationError(ValueError):
    """A question is malformed; the message is safe to show to the teacher."""


def _as_dict(q: Any) -> Dict[str, Any]:
    if isinstance(q, dict):
        return q
    if hasattr(q, "model_dump"):
        return q.model_dump()
    raise QuizValidationError("Question must be an object")


def normalise_question(q: Any) -> Dict[str, Any]:
    """Return a cleaned copy with a `type` field (default mcq) and stripped texts."""
    d = dict(_as_dict(q))
    d["type"] = (str(d.get("type") or "mcq")).strip().lower()
    d["question_text"] = str(d.get("question_text") or "").strip()
    d["options"] = [str(o).strip() for o in (d.get("options") or [])]
    if d["type"] == "true_false":
        d["options"] = list(TRUE_FALSE_OPTIONS)
    expl = d.get("explanation")
    d["explanation"] = (str(expl).strip() or None) if expl is not None else None
    return d


def validate_questions(questions: List[Any]) -> int:
    """Validate every question; return the total marks. Raises QuizValidationError."""
    if not questions:
        raise QuizValidationError("At least one question required")
    total = 0
    for i, raw in enumerate(questions, 1):
        q = _as_dict(raw)
        qtype = (str(q.get("type") or "mcq")).strip().lower()
        if qtype not in QUESTION_TYPES:
            raise QuizValidationError(f"Question {i}: unknown type '{qtype}' (use mcq or true_false)")
        if not str(q.get("question_text") or "").strip():
            raise QuizValidationError(f"Question {i}: text cannot be empty")
        options = list(q.get("options") or [])
        if any(not str(o).strip() for o in options):
            raise QuizValidationError(f"Question {i}: every option needs text")
        try:
            ci = int(q.get("correct_index"))
        except (TypeError, ValueError):
            raise QuizValidationError(f"Question {i}: correct_index must be a number")
        if qtype == "true_false":
            if len(options) != 2:
                raise QuizValidationError(f"Question {i}: a true/false question has exactly 2 options (True, False)")
            if ci not in (0, 1):
                raise QuizValidationError(f"Question {i}: correct_index must be 0 (True) or 1 (False)")
        else:
            if not 2 <= len(options) <= 6:
                raise QuizValidationError(f"Question {i}: must have 2 to 6 options")
            if not 0 <= ci < len(options):
                raise QuizValidationError(f"Question {i}: correct_index must be between 0 and {len(options) - 1}")
        marks = q.get("marks", 1)
        if not isinstance(marks, int) or isinstance(marks, bool) or marks < 1:
            raise QuizValidationError(f"Question {i}: marks must be >= 1")
        total += marks
    return total


def submission_window(quiz: Dict[str, Any], started_at: datetime, now: datetime,
                      grace_seconds: int = DEFAULT_GRACE_SECONDS) -> Dict[str, Any]:
    """
    ends_at = the sooner of (started_at + time limit) and the quiz deadline.
    The attempt is accepted until ends_at + grace; after that it is refused and
    `reason` says why ("time_limit" or "deadline"). late_by_seconds counts seconds past ends_at.
    """
    limit = timedelta(minutes=int(quiz.get("time_limit_minutes") or 0))
    ends_at = started_at + limit
    reason_if_closed = "time_limit"
    deadline = quiz.get("deadline")
    if deadline is not None and deadline < ends_at:
        ends_at = deadline
        reason_if_closed = "deadline"
    late_by = max(0, int((now - ends_at).total_seconds()))
    is_open = now <= ends_at + timedelta(seconds=grace_seconds)
    return {
        "ends_at": ends_at,
        "open": is_open,
        "late_by_seconds": late_by,
        "reason": None if is_open else reason_if_closed,
    }
