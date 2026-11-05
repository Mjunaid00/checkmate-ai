"""
Analytics helpers: score distribution buckets and weakest quiz questions.
Plus a regression test for the analytics route order (student deadlines were shadowed).
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_score_buckets_fixed_ranges_and_counts():
    from services.analytics_helpers import score_buckets
    out = score_buckets([0, 39.9, 40, 59.5, 60, 70, 89.9, 90, 100])
    assert [b["range"] for b in out] == ["0-39", "40-59", "60-69", "70-79", "80-89", "90-100"]
    assert [b["count"] for b in out] == [2, 2, 1, 1, 1, 2]


def test_score_buckets_empty_input_gives_zero_counts():
    from services.analytics_helpers import score_buckets
    assert all(b["count"] == 0 for b in score_buckets([]))


def test_weak_questions_sorted_by_lowest_correct_rate():
    from services.analytics_helpers import weak_questions
    quizzes = [
        {"_id": "q1", "title": "Quiz 1", "questions": [
            {"question_text": "Easy one", "correct_index": 0},
            {"question_text": "Hard one", "correct_index": 1},
        ]},
        {"_id": "q2", "title": "Quiz 2", "questions": [
            {"question_text": "Medium", "correct_index": 2},
        ]},
        {"_id": "q3", "title": "No attempts", "questions": [{"question_text": "x", "correct_index": 0}]},
    ]
    attempts = [
        {"quiz_id": "q1", "answers": [0, 0]},
        {"quiz_id": "q1", "answers": [0, 1]},
        {"quiz_id": "q1", "answers": [0, 0]},
        {"quiz_id": "q2", "answers": [2]},
        {"quiz_id": "q2", "answers": [1]},
    ]
    out = weak_questions(quizzes, attempts, limit=5)
    assert [(w["quiz_title"], w["question_index"]) for w in out] == [("Quiz 1", 1), ("Quiz 2", 0), ("Quiz 1", 0)]
    assert out[0]["correct_rate"] == 33.3 and out[0]["attempts"] == 3
    assert "No attempts" not in [w["quiz_title"] for w in out]


def test_weak_questions_respects_limit_and_truncates_text():
    from services.analytics_helpers import weak_questions
    quizzes = [{"_id": "q", "title": "Q", "questions": [{"question_text": "x" * 200, "correct_index": 0} for _ in range(3)]}]
    attempts = [{"quiz_id": "q", "answers": [1, 1, 1]}]
    out = weak_questions(quizzes, attempts, limit=2)
    assert len(out) == 2 and len(out[0]["question_text"]) <= 120


def test_student_deadlines_route_is_declared_before_student_id_route():
    from routers.analytics import router
    paths = [r.path for r in router.routes]
    assert paths.index("/analytics/student/deadlines") < paths.index("/analytics/student/{student_id}")
