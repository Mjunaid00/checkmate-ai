"""
Teacher Reports Router
- Class summary (per-assignment submission counts and stats)
- Student-by-student breakdown
- CSV downloads (class-wide and per-student)
"""
import csv
import io
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from bson import ObjectId
from database import get_db
from routers.deps import get_current_teacher
from services.report_rows import class_matrix_rows, student_rows
from services.xlsx_export import XLSX_MEDIA_TYPE, rows_to_xlsx_bytes

router = APIRouter(prefix="/reports", tags=["reports"])


def _csv_response(rows: list, filename: str) -> StreamingResponse:
    """Convert list of dicts to CSV streaming response."""
    if not rows:
        rows = [{"info": "No data available"}]
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=list(rows[0].keys()))
    writer.writeheader()
    writer.writerows(rows)
    buf.seek(0)
    return StreamingResponse(
        iter([buf.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _xlsx_response(rows: list, filename: str, title: str) -> StreamingResponse:
    data = rows_to_xlsx_bytes(rows, sheet_title=title)
    return StreamingResponse(
        iter([data]),
        media_type=XLSX_MEDIA_TYPE,
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def _safe(name: str, fallback: str) -> str:
    return "".join(c for c in (name or fallback) if c.isalnum() or c in (" ", "_", "-")).strip().replace(" ", "_") or fallback


async def _verify_teacher_owns_class(db, class_id: str, teacher_id: str) -> dict:
    """Verify the teacher owns this class. Returns the class doc."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")
    class_doc = await db["classes"].find_one({"_id": ObjectId(class_id), "teacher_id": teacher_id})
    if not class_doc:
        raise HTTPException(status_code=404, detail="Class not found")
    return class_doc


async def _get_class_data(db, class_id: str):
    """Fetch all data needed for class reports."""
    assignments = await db["assignments"].find({"class_id": class_id}).sort("created_at", 1).to_list(length=200)
    assignment_ids = [str(a["_id"]) for a in assignments]

    enrollments = await db["enrollments"].find({"class_id": class_id}).to_list(length=500)
    student_ids = list({e["student_id"] for e in enrollments})

    submissions = []
    if assignment_ids:
        cursor = db["submissions"].find({"assignment_id": {"$in": assignment_ids}})
        submissions = await cursor.to_list(length=2000)

    # Fetch student names
    students = {}
    if student_ids:
        valid_oids = [ObjectId(sid) for sid in student_ids if ObjectId.is_valid(sid)]
        cursor = db["users"].find({"_id": {"$in": valid_oids}})
        users = await cursor.to_list(length=500)
        students = {str(u["_id"]): {"name": u.get("name", "Unknown"), "email": u.get("email", "")} for u in users}

    quizzes = await db["quizzes"].find({"class_id": class_id}).sort("created_at", 1).to_list(length=200)
    quiz_ids = [str(z["_id"]) for z in quizzes]
    attempts = []
    if quiz_ids:
        attempts = await db["quiz_attempts"].find({"quiz_id": {"$in": quiz_ids}}).to_list(length=5000)

    return assignments, enrollments, submissions, students, quizzes, attempts


@router.get("/class/{class_id}/summary")
async def class_summary(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Per-assignment submission counts + per-student score breakdown for a class."""
    class_doc = await _verify_teacher_owns_class(db, class_id, current_teacher["id"])
    assignments, enrollments, submissions, students, quizzes, attempts = await _get_class_data(db, class_id)

    enrolled_count = len(enrollments)

    # Per-assignment stats
    assignment_stats = []
    for a in assignments:
        a_id = str(a["_id"])
        a_subs = [s for s in submissions if s["assignment_id"] == a_id]
        graded = [s for s in a_subs if s.get("status") == "graded" and s.get("score") is not None]
        scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in graded]

        assignment_stats.append({
            "assignment_id": a_id,
            "title": a.get("title", ""),
            "total_marks": a.get("total_marks", 0),
            "deadline": a.get("deadline").isoformat() if a.get("deadline") else None,
            "enrolled_students": enrolled_count,
            "submitted_count": len(a_subs),
            "graded_count": len(graded),
            "pending_count": len([s for s in a_subs if s.get("status") in ("uploaded", "processing")]),
            "failed_count": len([s for s in a_subs if s.get("status") == "failed"]),
            "submission_rate": round((len(a_subs) / enrolled_count) * 100, 1) if enrolled_count > 0 else 0,
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "highest_score": round(max(scores), 1) if scores else None,
            "lowest_score": round(min(scores), 1) if scores else None,
        })

    # Per-student stats
    student_stats = []
    for enr in enrollments:
        sid = enr["student_id"]
        s_subs = [s for s in submissions if s["student_id"] == sid]
        s_graded = [s for s in s_subs if s.get("status") == "graded" and s.get("score") is not None]
        scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in s_graded]

        student_stats.append({
            "student_id": sid,
            "name": students.get(sid, {}).get("name", "Unknown"),
            "email": students.get(sid, {}).get("email", ""),
            "total_assignments": len(assignments),
            "submitted": len(s_subs),
            "graded": len(s_graded),
            "average_score": round(sum(scores) / len(scores), 1) if scores else None,
            "completion_rate": round((len(s_subs) / len(assignments)) * 100, 1) if assignments else 0,
        })

    student_stats.sort(key=lambda x: (x["average_score"] or -1), reverse=True)

    # Overall class stats
    all_graded = [s for s in submissions if s.get("status") == "graded" and s.get("score") is not None]
    all_scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in all_graded]

    return {
        "class_id": class_id,
        "class_name": class_doc.get("name", ""),
        "max_students": class_doc.get("max_students"),
        "enrolled_count": enrolled_count,
        "total_assignments": len(assignments),
        "total_submissions": len(submissions),
        "total_graded": len(all_graded),
        "class_average": round(sum(all_scores) / len(all_scores), 1) if all_scores else None,
        "assignments": assignment_stats,
        "students": student_stats,
    }


async def _class_report_rows(db, class_id: str, teacher_id: str):
    """(class_doc, rows): one row per student x assessment (assignments and quizzes)."""
    class_doc = await _verify_teacher_owns_class(db, class_id, teacher_id)
    assignments, enrollments, submissions, students, quizzes, attempts = await _get_class_data(db, class_id)
    return class_doc, class_matrix_rows(assignments, quizzes, enrollments, submissions, attempts, students)


@router.get("/class/{class_id}/csv")
async def class_csv_report(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Download a CSV with one row per (student x assignment / quiz) - the full grade matrix."""
    class_doc, rows = await _class_report_rows(db, class_id, current_teacher["id"])
    filename = f"{_safe(class_doc.get('name'), 'class')}_report_{datetime.utcnow().strftime('%Y%m%d')}.csv"
    return _csv_response(rows, filename)


@router.get("/class/{class_id}/xlsx")
async def class_xlsx_report(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """The same grade matrix as an Excel workbook."""
    class_doc, rows = await _class_report_rows(db, class_id, current_teacher["id"])
    filename = f"{_safe(class_doc.get('name'), 'class')}_report_{datetime.utcnow().strftime('%Y%m%d')}.xlsx"
    return _xlsx_response(rows, filename, "Grades")


@router.get("/student/{student_id}/class/{class_id}")
async def student_class_report(
    student_id: str,
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Detailed report for a single student in a specific class."""
    class_doc = await _verify_teacher_owns_class(db, class_id, current_teacher["id"])
    assignments, enrollments, submissions, students, quizzes, attempts = await _get_class_data(db, class_id)

    if not any(e["student_id"] == student_id for e in enrollments):
        raise HTTPException(status_code=404, detail="Student not enrolled in this class")

    student = students.get(student_id, {"name": "Unknown", "email": ""})

    submission_details = []
    for a in assignments:
        a_id = str(a["_id"])
        sub = next((s for s in submissions if s["student_id"] == student_id and s["assignment_id"] == a_id), None)
        submission_details.append({
            "assignment_id": a_id,
            "assignment_title": a.get("title", ""),
            "total_marks": a.get("total_marks", 0),
            "deadline": a.get("deadline").isoformat() if a.get("deadline") else None,
            "submitted": sub is not None,
            "status": sub.get("status") if sub else "not_submitted",
            "score": sub.get("score") if sub else None,
            "percentage": round((sub["score"] / max(a.get("total_marks", 1), 1)) * 100, 1) if sub and sub.get("score") is not None else None,
            "submitted_at": sub.get("created_at").isoformat() if sub and sub.get("created_at") else None,
            "feedback": sub.get("feedback") if sub else None,
            "explainable_feedback": sub.get("explainable_feedback") if sub else None,
        })

    graded = [d for d in submission_details if d["score"] is not None]
    avg = round(sum(d["percentage"] for d in graded) / len(graded), 1) if graded else None

    return {
        "student": student,
        "class": {"class_id": class_id, "name": class_doc.get("name", "")},
        "summary": {
            "total_assignments": len(assignments),
            "submitted": sum(1 for d in submission_details if d["submitted"]),
            "graded": len(graded),
            "average_score": avg,
        },
        "submissions": submission_details,
    }


async def _student_report_rows(db, student_id: str, class_id: str, teacher_id: str):
    class_doc = await _verify_teacher_owns_class(db, class_id, teacher_id)
    assignments, enrollments, submissions, students, quizzes, attempts = await _get_class_data(db, class_id)
    if not any(e["student_id"] == student_id for e in enrollments):
        raise HTTPException(status_code=404, detail="Student not enrolled in this class")
    student = students.get(student_id, {"name": "Unknown", "email": ""})
    return class_doc, student, student_rows(student_id, assignments, quizzes, submissions, attempts)


def _student_filename(class_doc: dict, student: dict, ext: str) -> str:
    return f"{_safe(student.get('name'), 'student')}_{_safe(class_doc.get('name'), 'class')}_{datetime.utcnow().strftime('%Y%m%d')}.{ext}"


@router.get("/student/{student_id}/class/{class_id}/csv")
async def student_csv_report(
    student_id: str,
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Download a CSV report (assignments and quizzes) for a single student in a class."""
    class_doc, student, rows = await _student_report_rows(db, student_id, class_id, current_teacher["id"])
    return _csv_response(rows, _student_filename(class_doc, student, "csv"))


@router.get("/student/{student_id}/class/{class_id}/xlsx")
async def student_xlsx_report(
    student_id: str,
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """The same single-student report as an Excel workbook."""
    class_doc, student, rows = await _student_report_rows(db, student_id, class_id, current_teacher["id"])
    return _xlsx_response(rows, _student_filename(class_doc, student, "xlsx"), "Report")
