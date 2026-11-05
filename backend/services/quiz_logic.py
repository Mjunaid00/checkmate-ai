"""
Pure quiz rules shared by the quizzes router (no database, no FastAPI):

* validate_questions  - MCQ (2-6 options), true/false (True / False) and short-answer
                        (one or more accepted answers) questions
* normalise_question  - cleaned copy of a question for storage
* is_correct          - grade one answer against one question
* coerce_answers      - type-check a submitted answer list (ints for choice questions,
                        text for short answers)
* submission_window   - when an attempt must be in by, from the SERVER-side start time,
                        the quiz time limit and the deadline (whichever comes first)
"""
import re
from datetime import datetime, timedelta
from typing import Any, Dict, List

QUESTION_TYPES = ("mcq", "true_false", "short_answer")
TRUE_FALSE_OPTIONS = ["True", "False"]
DEFAULT_GRACE_SECONDS = 120  # network / clock slack before a late submission is refused
MAX_SHORT_ANSWER_CHARS = 500

_PUNCT_RE = re.compile(r"[^\w\s]", re.UNICODE)


class QuizValidationError(ValueError):
    """A question or answer is malformed; the message is safe to show to the user."""


def _as_dict(q: Any) -> Dict[str, Any]:
    if isinstance(q, dict):
        return q
    if hasattr(q, "model_dump"):
        return q.model_dump()
    raise QuizValidationError("Question must be an object")


def _qtype(q: Dict[str, Any]) -> str:
    return (str(q.get("type") or "mcq")).strip().lower()


def normalize_answer(value: Any) -> str:
    """Lower-case, drop punctuation, collapse whitespace: 'New   York, USA.' -> 'new york usa'."""
    if value is None:
        return ""
    text = _PUNCT_RE.sub(" ", str(value).lower())
    return " ".join(text.split())


def normalise_question(q: Any) -> Dict[str, Any]:
    """Return a cleaned copy with a `type` field (default mcq) and stripped texts."""
    d = dict(_as_dict(q))
    d["type"] = _qtype(d)
    d["question_text"] = str(d.get("question_text") or "").strip()
    d["options"] = [str(o).strip() for o in (d.get("options") or [])]
    expl = d.get("explanation")
    d["explanation"] = (str(expl).strip() or None) if expl is not None else None
    if d["type"] == "true_false":
        d["options"] = list(TRUE_FALSE_OPTIONS)
        d["accepted_answers"] = None
    elif d["type"] == "short_answer":
        seen, accepted = set(), []
        for a in d.get("accepted_answers") or []:
            text = str(a).strip()
            key = normalize_answer(text)
            if key and key not in seen:
                seen.add(key)
                accepted.append(text)
        d["accepted_answers"] = accepted
        d["options"] = []
        d["correct_index"] = None
    else:
        d["accepted_answers"] = None
    return d


def validate_questions(questions: List[Any]) -> int:
    """Validate every question; return the total marks. Raises QuizValidationError."""
    if not questions:
        raise QuizValidationError("At least one question required")
    total = 0
    for i, raw in enumerate(questions, 1):
        q = _as_dict(raw)
        qtype = _qtype(q)
        if qtype not in QUESTION_TYPES:
            raise QuizValidationError(f"Question {i}: unknown type '{qtype}' (use mcq, true_false or short_answer)")
        if not str(q.get("question_text") or "").strip():
            raise QuizValidationError(f"Question {i}: text cannot be empty")
        if qtype == "short_answer":
            accepted = [a for a in (q.get("accepted_answers") or []) if str(a).strip()]
            if not accepted:
                raise QuizValidationError(f"Question {i}: a short-answer question needs at least one accepted answer")
        else:
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


def is_correct(question: Dict[str, Any], answer: Any) -> bool:
    """Grade one submitted answer. Unanswered (-1, '' or None) is never correct."""
    if _qtype(question) == "short_answer":
        if answer is None or isinstance(answer, bool) or not isinstance(answer, str):
            return False
        given = normalize_answer(answer)
        if not given:
            return False
        return given in {normalize_answer(a) for a in (question.get("accepted_answers") or [])}
    if isinstance(answer, bool) or not isinstance(answer, int) or answer < 0:
        return False
    return answer == question.get("correct_index")


def coerce_answers(questions: List[Dict[str, Any]], answers: List[Any]) -> List[Any]:
    """
    Check one submitted answer per question and return the cleaned list:
    option index (-1 = unanswered) for choice questions, stripped text ('' = unanswered)
    for short answers. Raises QuizValidationError on a wrong count or type.
    """
    if len(answers) != len(questions):
        raise QuizValidationError(f"Expected {len(questions)} answers, got {len(answers)}")
    out: List[Any] = []
    for i, (q, a) in enumerate(zip(questions, answers), 1):
        if _qtype(q) == "short_answer":
            if a is None or (isinstance(a, int) and not isinstance(a, bool) and a < 0):
                out.append("")
                continue
            if not isinstance(a, str):
                raise QuizValidationError(f"Question {i}: expected a text answer")
            out.append(a.strip()[:MAX_SHORT_ANSWER_CHARS])
        else:
            if a is None:
                out.append(-1)
                continue
            if isinstance(a, bool) or not isinstance(a, int):
                raise QuizValidationError(f"Question {i}: expected an option index")
            if a < -1 or a >= len(q.get("options") or []):
                raise QuizValidationError(f"Question {i}: option index {a} is out of range")
            out.append(a)
    return out


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
