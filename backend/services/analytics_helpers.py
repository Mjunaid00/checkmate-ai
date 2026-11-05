"""
Pure helpers for the teacher analytics overview.
"""
from typing import Any, Dict, Iterable, List

from services.quiz_logic import is_correct

SCORE_BUCKETS = [(0, 40, "0-39"), (40, 60, "40-59"), (60, 70, "60-69"), (70, 80, "70-79"), (80, 90, "80-89"), (90, 101, "90-100")]


def score_buckets(percentages: Iterable[float]) -> List[Dict[str, Any]]:
    """Count percentage scores into fixed grade bands (100 lands in the top band)."""
    counts = [0] * len(SCORE_BUCKETS)
    for p in percentages:
        try:
            v = float(p)
        except (TypeError, ValueError):
            continue
        v = max(0.0, min(100.0, v))
        for i, (lo, hi, _label) in enumerate(SCORE_BUCKETS):
            if lo <= v < hi:
                counts[i] += 1
                break
    return [{"range": label, "count": counts[i]} for i, (_lo, _hi, label) in enumerate(SCORE_BUCKETS)]


def weak_questions(quizzes: List[Dict[str, Any]], attempts: List[Dict[str, Any]], limit: int = 5) -> List[Dict[str, Any]]:
    """
    Questions with the lowest correct rate across all quizzes (only quizzes with attempts).
    Sorted ascending by correct_rate; ties keep quiz order.
    """
    by_quiz: Dict[str, List[Dict[str, Any]]] = {}
    for a in attempts:
        by_quiz.setdefault(str(a.get("quiz_id")), []).append(a)
    rows: List[Dict[str, Any]] = []
    for quiz in quizzes:
        qid = str(quiz.get("_id", quiz.get("quiz_id")))
        quiz_attempts = by_quiz.get(qid) or []
        if not quiz_attempts:
            continue
        for idx, q in enumerate(quiz.get("questions") or []):
            correct = sum(
                1 for a in quiz_attempts
                if idx < len(a.get("answers") or []) and is_correct(q, a["answers"][idx])
            )
            rows.append({
                "quiz_id": qid,
                "quiz_title": quiz.get("title", ""),
                "question_index": idx,
                "question_text": str(q.get("question_text", ""))[:120],
                "attempts": len(quiz_attempts),
                "correct_rate": round(correct / len(quiz_attempts) * 100, 1),
            })
    rows.sort(key=lambda r: r["correct_rate"])
    return rows[:max(0, int(limit))]
