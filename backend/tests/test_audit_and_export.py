"""
Audit entries for teacher overrides, Excel export, and the report row builders.
"""
import io
import sys
from datetime import datetime
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


# ── audit ────────────────────────────────────────────────────────────────────

def test_audit_entry_shape():
    from services.audit import audit_entry
    actor = {"id": "t1", "name": "Ms T", "role": "teacher"}
    e = audit_entry(actor, "quiz_attempt_reset", "quiz", "q1", reason="  Student's browser crashed  ", details={"student_id": "s1"})
    assert e["actor_id"] == "t1" and e["actor_name"] == "Ms T" and e["actor_role"] == "teacher"
    assert e["action"] == "quiz_attempt_reset" and e["target_type"] == "quiz" and e["target_id"] == "q1"
    assert e["reason"] == "Student's browser crashed"
    assert e["details"] == {"student_id": "s1"}
    assert isinstance(e["created_at"], datetime)


def test_audit_entry_requires_a_reason():
    from services.audit import audit_entry, AuditError
    actor = {"id": "t1", "name": "Ms T", "role": "teacher"}
    with pytest.raises(AuditError):
        audit_entry(actor, "quiz_attempt_reset", "quiz", "q1", reason="  ")
    with pytest.raises(AuditError):
        audit_entry(actor, "quiz_attempt_reset", "quiz", "q1", reason="ok")  # too short


# ── xlsx ─────────────────────────────────────────────────────────────────────

def test_rows_to_xlsx_round_trip():
    from openpyxl import load_workbook
    from services.xlsx_export import rows_to_xlsx_bytes
    data = rows_to_xlsx_bytes([{"Student": "Ann", "Score": 7}, {"Student": "Bob", "Score": None}], sheet_title="Grades")
    assert data[:2] == b"PK"
    wb = load_workbook(io.BytesIO(data))
    ws = wb["Grades"]
    assert [c.value for c in ws[1]] == ["Student", "Score"]
    assert [c.value for c in ws[2]] == ["Ann", 7]
    assert ws[3][1].value is None


def test_rows_to_xlsx_empty_gives_info_row():
    from openpyxl import load_workbook
    from services.xlsx_export import rows_to_xlsx_bytes
    wb = load_workbook(io.BytesIO(rows_to_xlsx_bytes([], sheet_title="Empty")))
    assert wb["Empty"][1][0].value == "info"


# ── report rows ──────────────────────────────────────────────────────────────

def _data():
    assignments = [{"_id": "a1", "title": "Essay", "total_marks": 10, "deadline": datetime(2026, 11, 10, 9, 0)}]
    quizzes = [{"_id": "z1", "title": "Quiz 1", "total_marks": 4, "deadline": None}]
    enrollments = [{"student_id": "s1"}, {"student_id": "s2"}]
    submissions = [{"student_id": "s1", "assignment_id": "a1", "status": "graded", "score": 7, "created_at": datetime(2026, 11, 9, 8, 0), "feedback": "good\nwork"}]
    attempts = [{"student_id": "s2", "quiz_id": "z1", "score": 3, "total_marks": 4, "submitted_at": datetime(2026, 11, 9, 10, 0), "status": "submitted"}]
    students = {"s1": {"name": "Ann", "email": "ann@x"}, "s2": {"name": "Bob", "email": "bob@x"}}
    return assignments, quizzes, enrollments, submissions, attempts, students


def test_class_matrix_rows_cover_assignments_and_quizzes():
    from services.report_rows import class_matrix_rows
    rows = class_matrix_rows(*_data())
    assert len(rows) == 4  # 2 students x (1 assignment + 1 quiz)
    ann_essay = next(r for r in rows if r["Student Name"] == "Ann" and r["Type"] == "Assignment")
    assert ann_essay["Score"] == 7 and ann_essay["Percentage"] == "70.0%" and ann_essay["Feedback"] == "good work"
    bob_quiz = next(r for r in rows if r["Student Name"] == "Bob" and r["Type"] == "Quiz")
    assert bob_quiz["Status"] == "submitted" and bob_quiz["Score"] == 3 and bob_quiz["Percentage"] == "75.0%"
    ann_quiz = next(r for r in rows if r["Student Name"] == "Ann" and r["Type"] == "Quiz")
    assert ann_quiz["Status"] == "Not Attempted" and ann_quiz["Score"] == ""
    assert list(rows[0].keys())[:4] == ["Student Name", "Student Email", "Type", "Title"]


def test_student_rows_for_one_student():
    from services.report_rows import student_rows
    assignments, quizzes, enrollments, submissions, attempts, students = _data()
    rows = student_rows("s2", assignments, quizzes, submissions, attempts)
    assert [(r["Type"], r["Status"]) for r in rows] == [("Assignment", "Not Submitted"), ("Quiz", "submitted")]


def test_audit_entry_without_reason_is_allowed_only_when_not_required():
    from services.audit import audit_entry, AuditError
    actor = {"id": "a1", "name": "Admin", "role": "admin"}
    entry = audit_entry(actor, "user_deleted", "user", "u1", None, {"email": "x@y.z"}, require_reason=False)
    assert entry["reason"] == "" and entry["action"] == "user_deleted" and entry["details"] == {"email": "x@y.z"}
    with pytest.raises(AuditError):
        audit_entry(actor, "submission_reset", "submission", "s1", None, require_reason=True)
