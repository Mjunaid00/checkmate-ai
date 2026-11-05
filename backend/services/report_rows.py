"""
Row builders shared by the CSV and Excel class reports: one row per student per
assessment (assignments AND quizzes).
"""
from typing import Any, Dict, List


def _fmt(dt) -> str:
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ""


def _pct(score, total) -> str:
    return f"{(score / max(total or 1, 1)) * 100:.1f}%"


def _assignment_row(a: Dict[str, Any], sub: Dict[str, Any] | None) -> Dict[str, Any]:
    has_score = bool(sub) and sub.get("score") is not None
    return {
        "Type": "Assignment",
        "Title": a.get("title", ""),
        "Total Marks": a.get("total_marks", 0),
        "Deadline": _fmt(a.get("deadline")),
        "Status": sub.get("status") if sub else "Not Submitted",
        "Score": sub.get("score") if has_score else "",
        "Percentage": _pct(sub["score"], a.get("total_marks", 1)) if has_score else "",
        "Submitted At": _fmt(sub.get("created_at")) if sub else "",
        "Feedback": (sub.get("feedback") or "").replace("\n", " ") if sub else "",
    }


def _quiz_row(z: Dict[str, Any], att: Dict[str, Any] | None) -> Dict[str, Any]:
    has_score = bool(att) and att.get("score") is not None
    return {
        "Type": "Quiz",
        "Title": z.get("title", ""),
        "Total Marks": z.get("total_marks", 0),
        "Deadline": _fmt(z.get("deadline")),
        "Status": att.get("status", "submitted") if att else "Not Attempted",
        "Score": att.get("score") if has_score else "",
        "Percentage": _pct(att["score"], att.get("total_marks") or z.get("total_marks", 1)) if has_score else "",
        "Submitted At": _fmt(att.get("submitted_at")) if att else "",
        "Feedback": "",
    }


def student_rows(student_id: str, assignments: List[Dict], quizzes: List[Dict],
                 submissions: List[Dict], attempts: List[Dict]) -> List[Dict[str, Any]]:
    rows = []
    for a in assignments:
        a_id = str(a["_id"])
        sub = next((s for s in submissions if s.get("student_id") == student_id and s.get("assignment_id") == a_id), None)
        rows.append(_assignment_row(a, sub))
    for z in quizzes:
        z_id = str(z["_id"])
        att = next((t for t in attempts if t.get("student_id") == student_id and t.get("quiz_id") == z_id), None)
        rows.append(_quiz_row(z, att))
    return rows


def class_matrix_rows(assignments: List[Dict], quizzes: List[Dict], enrollments: List[Dict],
                      submissions: List[Dict], attempts: List[Dict], students: Dict[str, Dict]) -> List[Dict[str, Any]]:
    rows = []
    for enr in enrollments:
        sid = enr["student_id"]
        info = students.get(sid, {})
        prefix = {"Student Name": info.get("name", "Unknown"), "Student Email": info.get("email", "")}
        for r in student_rows(sid, assignments, quizzes, submissions, attempts):
            rows.append({**prefix, **r})
    return rows
