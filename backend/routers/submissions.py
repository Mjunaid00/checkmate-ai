from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks
from typing import Optional
from pydantic import BaseModel
import asyncio
import os
import re
import tempfile
from datetime import datetime
from pathlib import Path
from bson import ObjectId

from config import (
    UPLOAD_DIR,
    MAX_UPLOAD_SIZE_MB,
    OCR_BACKEND,
    REQUIRE_INSTITUTION_HEADER,
    relative_upload_path,
)
from database import get_db
from services.student_safe import redact_keyword_analysis
from services.permissions import can_manage, is_admin_override
from services.audit import AuditError, record_audit
import shutil
from models.school import SubmissionOut
from routers.deps import get_current_student, get_current_user, get_current_teacher
from services.grading import process_exam_background
from services.notifications import notify_user

router = APIRouter(prefix="/submissions", tags=["submissions"])


class ManualGradeBody(BaseModel):
    score: float
    feedback: Optional[str] = None

EXPECTED_INSTITUTION = "Shaheed Zulfikar Ali Bhutto Institute of Science and Technology University"
_HEADER_KEYWORDS = ("shaheed", "zulfikar", "bhutto", "institute", "science", "technology", "university")
_HEADER_MIN_MATCHES = 4  # OCR-tolerant: accept if most distinctive words are recognized
_HEADER_SCAN_CHARS = 1500  # only look near the top of the page


def _contains_institution_header(text: str) -> bool:
    """Tolerant check for the institution name. Robust to OCR noise and casing."""
    if not text:
        return False
    head = re.sub(r"\s+", " ", text[:_HEADER_SCAN_CHARS].lower())
    if "szabist" in head:
        return True
    matches = sum(1 for kw in _HEADER_KEYWORDS if kw in head)
    return matches >= _HEADER_MIN_MATCHES


def _check_header_in_bytes(content: bytes, extension: str) -> bool:
    """OCR the first page of an in-memory file and verify the institution header."""
    from services.ocr import extract_text_from_first_page
    with tempfile.NamedTemporaryFile(delete=False, suffix=extension) as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    try:
        text = extract_text_from_first_page(tmp_path)
        return _contains_institution_header(text)
    finally:
        try:
            tmp_path.unlink()
        except OSError:
            pass


def map_submission(doc: dict) -> dict:
    doc["submission_id"] = str(doc["_id"])
    return doc


@router.post("/", response_model=SubmissionOut)
async def upload_submission(
    background_tasks: BackgroundTasks,
    assignment_id: str = Form(...),
    file: UploadFile = File(...),
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student uploads their answer to an assignment. Single submission per student."""
    if not ObjectId.is_valid(assignment_id):
        raise HTTPException(status_code=400, detail="Invalid assignment_id")

    assignment = await db["assignments"].find_one({"_id": ObjectId(assignment_id)})
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    # Verify enrollment
    enrollment = await db["enrollments"].find_one({
        "class_id": assignment["class_id"],
        "student_id": current_student["id"]
    })
    if not enrollment:
        raise HTTPException(status_code=403, detail="You must enroll in this class before submitting")

    # Block duplicate submissions
    existing = await db["submissions"].find_one({
        "assignment_id": assignment_id,
        "student_id": current_student["id"],
    })
    if existing:
        raise HTTPException(status_code=409, detail="You have already submitted an answer for this assignment. Submissions cannot be re-uploaded.")

    # Deadline check
    if assignment.get("deadline") and datetime.utcnow() > assignment["deadline"]:
        raise HTTPException(status_code=403, detail="Submission deadline has passed")

    # Per-assignment format validation
    from services.plagiarism import validate_format
    ok, msg = validate_format(
        file.filename or "",
        file.content_type,
        assignment.get("allowed_formats"),
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)

    # Read the upload into memory so we can validate the header before persisting.
    try:
        content = await file.read()
    finally:
        file.file.close()

    extension = os.path.splitext(file.filename or "")[1].lower()

    if not content:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(content) > MAX_UPLOAD_SIZE_MB * 1024 * 1024:
        raise HTTPException(status_code=413, detail=f"File too large. Maximum size is {MAX_UPLOAD_SIZE_MB} MB.")

    # Header validation: the first page must contain the institution name.
    # OCR is blocking model inference, so it runs in a worker thread.
    header_ok = True
    if REQUIRE_INSTITUTION_HEADER and OCR_BACKEND != "none":
        try:
            header_ok = await asyncio.to_thread(_check_header_in_bytes, content, extension)
        except Exception as e:
            print(f"[Submission] header OCR failed: {e}")
            raise HTTPException(
                status_code=503,
                detail="Could not verify your file's header right now (OCR service unavailable). Please try again in a moment.",
            )
    if not header_ok:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Your submission must include the institution header '{EXPECTED_INSTITUTION}' "
                "at the top of the first page. Please add it and upload again."
            ),
        )

    record = {
        "assignment_id": assignment_id,
        "student_id": current_student["id"],
        "student_id_number": enrollment.get("student_id_number"),
        "original_name": file.filename,
        "file_type": file.content_type,
        "status": "uploaded",
        "total_marks": assignment["total_marks"],
        "created_at": datetime.utcnow(),
    }
    result = await db["submissions"].insert_one(record)
    submission_id = str(result.inserted_id)

    folder = UPLOAD_DIR / "submissions" / submission_id
    folder.mkdir(parents=True, exist_ok=True)
    save_path = folder / f"answer{extension}"

    try:
        with save_path.open("wb") as buffer:
            buffer.write(content)
    except Exception as e:
        await db["submissions"].delete_one({"_id": result.inserted_id})
        raise HTTPException(status_code=500, detail="Storage failed")

    str_save_path = relative_upload_path(save_path)
    await db["submissions"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"answer_file_path": str_save_path}}
    )

    # Notify teacher of new submission
    await notify_user(
        db,
        user_id=assignment["teacher_id"],
        title="New submission received",
        body=f"{current_student.get('name', 'A student')} submitted '{assignment.get('title', 'an assignment')}'",
        link="/",
        category="submission",
    )

    # Dispatch grading
    background_tasks.add_task(
        process_exam_background,
        submission_id,
        assignment.get("rubric_file_path") or "",
        str_save_path,
        assignment["total_marks"],
        assignment.get("grading_prompt"),
    )

    record["_id"] = result.inserted_id
    return map_submission(record)


@router.get("/student", response_model=list[SubmissionOut])
async def list_my_submissions(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Students see their own submissions (rubric keyword lists only after the deadline)."""
    cursor = db["submissions"].find({"student_id": current_student["id"]}).sort("created_at", -1)
    results = await cursor.to_list(length=100)
    a_ids = [ObjectId(x["assignment_id"]) for x in results if ObjectId.is_valid(str(x.get("assignment_id", "")))]
    deadlines = {}
    if a_ids:
        for a in await db["assignments"].find({"_id": {"$in": a_ids}}, {"deadline": 1}).to_list(length=200):
            deadlines[str(a["_id"])] = a.get("deadline")
    now = datetime.utcnow()
    return [redact_keyword_analysis(map_submission(x), deadlines.get(str(x.get("assignment_id"))), now) for x in results]


@router.get("/assignment/{assignment_id}", response_model=list[SubmissionOut])
async def list_assignment_submissions(
    assignment_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Teachers see every submission for their own assignment; students see only their own."""
    if not ObjectId.is_valid(assignment_id):
        raise HTTPException(status_code=400, detail="Invalid assignment_id")

    query = {"assignment_id": assignment_id}
    if current_user.get("role") == "student":
        query["student_id"] = current_user["id"]
    else:
        assignment = await db["assignments"].find_one({"_id": ObjectId(assignment_id)})
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if current_user.get("role") != "admin" and assignment.get("teacher_id") != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not authorized to view these submissions")

    cursor = db["submissions"].find(query).sort("created_at", -1)
    results = await cursor.to_list(length=100)
    return [map_submission(s) for s in results]


@router.patch("/{submission_id}/grade", response_model=SubmissionOut)
async def manual_grade(
    submission_id: str,
    body: ManualGradeBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher manually grades or overrides AI score for a submission."""
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission_id")

    sub = await db["submissions"].find_one({"_id": ObjectId(submission_id)})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")

    # Verify the assignment belongs to this teacher
    if not ObjectId.is_valid(sub["assignment_id"]):
        raise HTTPException(status_code=400, detail="Invalid assignment reference")
    assignment = await db["assignments"].find_one({"_id": ObjectId(sub["assignment_id"])})
    if not assignment or assignment.get("teacher_id") != current_teacher["id"]:
        raise HTTPException(status_code=403, detail="Not authorized to grade this submission")

    if body.score < 0:
        raise HTTPException(status_code=400, detail="Score cannot be negative")
    total = sub.get("total_marks") or assignment.get("total_marks") or 0
    if total > 0 and body.score > total:
        raise HTTPException(status_code=400, detail=f"Score cannot exceed {total}")

    updates = {
        "manual_score": body.score,
        "manual_feedback": body.feedback.strip() if body.feedback else None,
        "manually_graded_at": datetime.utcnow(),
        "manually_graded_by": current_teacher["id"],
        "score": int(round(body.score)),  # Override displayed score
        "status": "graded",
    }
    if body.feedback:
        updates["feedback"] = body.feedback.strip()

    await db["submissions"].update_one(
        {"_id": ObjectId(submission_id)},
        {"$set": updates},
    )

    # Notify student of manual grade
    await notify_user(
        db,
        user_id=sub["student_id"],
        title="Your submission was graded by teacher",
        body=f"'{assignment.get('title', 'Assignment')}' — scored {body.score}/{total}",
        link="/",
        category="grading",
    )

    updated = await db["submissions"].find_one({"_id": ObjectId(submission_id)})
    return map_submission(updated)


class AllowResubmissionBody(BaseModel):
    reason: str


@router.post("/{submission_id}/allow-resubmission")
async def allow_resubmission(
    submission_id: str,
    body: AllowResubmissionBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Teacher override of the single-submission rule: deletes the student's submission (record
    and file) so they can upload again. Needs a reason; the override is written to the audit log.
    """
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission_id")
    sub = await db["submissions"].find_one({"_id": ObjectId(submission_id)})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    if not ObjectId.is_valid(sub["assignment_id"]):
        raise HTTPException(status_code=400, detail="Invalid assignment reference")
    assignment = await db["assignments"].find_one({"_id": ObjectId(sub["assignment_id"])})
    if not assignment or not can_manage(current_teacher, assignment.get("teacher_id")):
        raise HTTPException(status_code=403, detail="Not authorized to change this submission")
    by_admin = is_admin_override(current_teacher, assignment.get("teacher_id"))
    try:
        await record_audit(
            db, current_teacher, "submission_reset", "submission", submission_id, body.reason,
            details={
                "assignment_id": sub["assignment_id"], "assignment_title": assignment.get("title"),
                "student_id": sub["student_id"], "previous_status": sub.get("status"),
                "previous_score": sub.get("score"), "file": sub.get("answer_file_path"),
            },
        )
    except AuditError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db["submissions"].delete_one({"_id": ObjectId(submission_id)})
    folder = UPLOAD_DIR / "submissions" / submission_id
    if folder.is_dir():
        shutil.rmtree(folder, ignore_errors=True)
    await notify_user(
        db,
        user_id=sub["student_id"],
        title="You may submit again",
        body=(f"An administrator removed your submission for '{assignment.get('title', 'the assignment')}' at request "
              f"({body.reason.strip()}). You may upload again." if by_admin else
              f"Your teacher allowed a new submission for '{assignment.get('title', 'the assignment')}' ({body.reason.strip()})"),
        link="/",
        category="grading",
    )
    return {"allowed": True, "submission_id": submission_id, "student_id": sub["student_id"]}


@router.post("/assignment/{assignment_id}/check-plagiarism")
async def check_plagiarism(
    assignment_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher triggers similarity check across all submissions for an assignment."""
    if not ObjectId.is_valid(assignment_id):
        raise HTTPException(status_code=400, detail="Invalid assignment_id")

    assignment = await db["assignments"].find_one({
        "_id": ObjectId(assignment_id), "teacher_id": current_teacher["id"]
    })
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    from services.plagiarism import check_assignment_plagiarism
    result = await check_assignment_plagiarism(db, assignment_id)
    return result
