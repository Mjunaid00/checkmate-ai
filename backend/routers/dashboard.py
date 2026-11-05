from fastapi import APIRouter, Depends, HTTPException, status
from typing import List, Dict, Any
from bson import ObjectId

from database import get_db
from models.school import SubmissionOut
from routers.deps import get_current_teacher

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


def map_exam(exam: dict) -> dict:
    """Helper to map MongoDB _id to string for Pydantic schemas"""
    exam["submission_id"] = str(exam["_id"])
    return exam


def summarize_submissions(submissions: List[dict]) -> Dict[str, Any]:
    """Totals + marks-weighted average percentage over graded submissions."""
    graded = [s for s in submissions if s.get("status") == "graded" and s.get("score") is not None]
    score_sum = sum(float(s["score"]) for s in graded)
    marks_sum = sum(float(s.get("total_marks") or 0) for s in graded)
    avg = round((score_sum / marks_sum) * 100, 2) if marks_sum > 0 else 0.0
    return {
        "total_exams": len(submissions),
        "graded_exams": len(graded),
        "average_percentage": avg,
    }


async def _teacher_submissions(db, teacher_id: str, limit: int = 2000) -> List[dict]:
    """
    Submissions do not carry teacher_id; they belong to a teacher through the
    assignment. Resolve the teacher's assignments first, then their submissions.
    """
    assignments = await db["assignments"].find({"teacher_id": teacher_id}, {"_id": 1}).to_list(length=None)
    assignment_ids = [str(a["_id"]) for a in assignments]
    if not assignment_ids:
        return []
    cursor = db["submissions"].find({"assignment_id": {"$in": assignment_ids}}).sort("created_at", -1)
    return await cursor.to_list(length=limit)


@router.get("/stats", response_model=Dict[str, Any])
async def get_dashboard_stats(
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Returns aggregated statistics for the logged-in teacher:
    - Total submissions across their assignments
    - Number of graded submissions
    - Marks-weighted average percentage over graded submissions
    """
    submissions = await _teacher_submissions(db, current_teacher["id"])
    return summarize_submissions(submissions)


@router.get("/exams", response_model=List[SubmissionOut])
async def list_exams(
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """List the 100 most recent submissions for assignments authored by this teacher."""
    submissions = await _teacher_submissions(db, current_teacher["id"], limit=100)
    return [map_exam(sub) for sub in submissions]


@router.get("/exams/{exam_id}", response_model=SubmissionOut)
async def get_exam_details(
    exam_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Fetch a single submission (with grading feedback). Only the owning teacher may view it."""
    if not ObjectId.is_valid(exam_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid Exam ID")

    exam = await db["submissions"].find_one({"_id": ObjectId(exam_id)})
    if not exam:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Submission not found")

    assignment = None
    if ObjectId.is_valid(exam.get("assignment_id", "")):
        assignment = await db["assignments"].find_one({"_id": ObjectId(exam["assignment_id"])})
    if not assignment or assignment.get("teacher_id") != current_teacher["id"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to view this submission")

    return map_exam(exam)
