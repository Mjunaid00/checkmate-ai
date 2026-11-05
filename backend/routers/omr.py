"""
OMR Router — Optical Mark Recognition for MCQ + True/False sheets.

Teacher creates a template (answer key), then either:
- A student uploads a single filled sheet, or
- The teacher batch-uploads multiple filled sheets.

Each submission is processed in the background by the LM Studio vision model.
"""
import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Literal
from fastapi import APIRouter, Depends, HTTPException, File, UploadFile, Form, BackgroundTasks
from pydantic import BaseModel
from bson import ObjectId

from config import UPLOAD_DIR, relative_upload_path
from core.timeutil import parse_deadline
from database import get_db
from models.omr import OMRTemplateOut, OMRSubmissionOut
from routers.deps import get_current_teacher, get_current_student, get_current_user
from services.omr_processor import process_omr_sheet
from services.notifications import notify_user

router = APIRouter(prefix="/omr", tags=["omr"])

ALLOWED_TYPES = ["application/pdf", "image/jpeg", "image/png"]


# ── Request bodies ──────────────────────────────────────────────────────────
class TemplateCreate(BaseModel):
    class_id: str
    title: str
    description: Optional[str] = None
    sheet_type: Literal["mcq", "true_false"] = "mcq"
    num_questions: int
    options_per_question: int = 4
    answer_key: List[int]
    marks_per_question: int = 1
    negative_marking: float = 0.0
    deadline: Optional[str] = None


# ── Helpers ─────────────────────────────────────────────────────────────────
def _map_template(doc: dict, hide_key: bool = False) -> dict:
    out = dict(doc)
    out["template_id"] = str(doc["_id"])
    out.pop("_id", None)
    if hide_key:
        out["answer_key"] = None
    return out


def _map_submission(doc: dict) -> dict:
    out = dict(doc)
    out["submission_id"] = str(doc["_id"])
    out.pop("_id", None)
    return out


async def _verify_class_owned(db, class_id: str, teacher_id: str):
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")
    cls = await db["classes"].find_one({"_id": ObjectId(class_id), "teacher_id": teacher_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


async def _verify_enrolled(db, class_id: str, student_id: str):
    enr = await db["enrollments"].find_one({"class_id": class_id, "student_id": student_id})
    if not enr:
        raise HTTPException(status_code=403, detail="Enroll in this class first")
    return enr


def _validate_template_body(body: TemplateCreate) -> int:
    """Validate template inputs and return total_marks."""
    if not body.title.strip():
        raise HTTPException(status_code=400, detail="Title is required")
    if body.num_questions < 1 or body.num_questions > 200:
        raise HTTPException(status_code=400, detail="num_questions must be 1-200")
    if body.sheet_type == "true_false":
        body.options_per_question = 2
    if body.options_per_question < 2 or body.options_per_question > 6:
        raise HTTPException(status_code=400, detail="options_per_question must be 2-6")
    if len(body.answer_key) != body.num_questions:
        raise HTTPException(status_code=400, detail=f"answer_key must have {body.num_questions} entries")
    for i, a in enumerate(body.answer_key):
        if not isinstance(a, int) or a < 0 or a >= body.options_per_question:
            raise HTTPException(status_code=400, detail=f"answer_key[{i}] out of range 0..{body.options_per_question - 1}")
    if body.marks_per_question < 1:
        raise HTTPException(status_code=400, detail="marks_per_question must be >= 1")
    if body.negative_marking < 0:
        raise HTTPException(status_code=400, detail="negative_marking cannot be negative")
    return body.num_questions * body.marks_per_question


# ── Templates (Teacher CRUD) ────────────────────────────────────────────────
@router.post("/templates", response_model=OMRTemplateOut)
async def create_template(
    body: TemplateCreate,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    await _verify_class_owned(db, body.class_id, current_teacher["id"])
    total_marks = _validate_template_body(body)

    deadline = None
    if body.deadline and body.deadline.strip():
        try:
            deadline = parse_deadline(body.deadline)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid deadline format")
        if deadline < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Deadline cannot be in the past")

    record = {
        "class_id": body.class_id,
        "teacher_id": current_teacher["id"],
        "title": body.title.strip(),
        "description": body.description.strip() if body.description else None,
        "sheet_type": body.sheet_type,
        "num_questions": body.num_questions,
        "options_per_question": body.options_per_question,
        "answer_key": body.answer_key,
        "marks_per_question": body.marks_per_question,
        "total_marks": total_marks,
        "negative_marking": body.negative_marking,
        "deadline": deadline,
        "created_at": datetime.utcnow(),
    }
    result = await db["omr_templates"].insert_one(record)
    record["_id"] = result.inserted_id

    # Notify enrolled students
    cls = await db["classes"].find_one({"_id": ObjectId(body.class_id)})
    enrolled = await db["enrollments"].find({"class_id": body.class_id}).to_list(length=500)
    for enr in enrolled:
        await notify_user(
            db,
            user_id=enr["student_id"],
            title="New OMR sheet posted",
            body=f"'{body.title}' is available in {cls.get('name', 'your class') if cls else 'your class'} ({body.num_questions} questions)",
            link="/",
            category="omr",
        )

    return _map_template(record)


@router.get("/templates/class/{class_id}", response_model=List[OMRTemplateOut])
async def list_templates(
    class_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List OMR templates for a class. Students see them with answer key hidden."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    if current_user["role"] == "student":
        await _verify_enrolled(db, class_id, current_user["id"])

    cursor = db["omr_templates"].find({"class_id": class_id}).sort("created_at", -1)
    templates = await cursor.to_list(length=200)

    is_student = current_user["role"] == "student"
    out = []
    for t in templates:
        mapped = _map_template(t, hide_key=is_student)
        if is_student:
            sub = await db["omr_submissions"].find_one({
                "template_id": mapped["template_id"],
                "submitter_id": current_user["id"],
                "submitter_role": "student",
            })
            mapped["has_submitted"] = sub is not None
        else:
            mapped["submission_count"] = await db["omr_submissions"].count_documents({
                "template_id": mapped["template_id"]
            })
        out.append(mapped)
    return out


@router.delete("/templates/{template_id}", status_code=204)
async def delete_template(
    template_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template_id")
    template = await db["omr_templates"].find_one({
        "_id": ObjectId(template_id), "teacher_id": current_teacher["id"]
    })
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")
    await db["omr_submissions"].delete_many({"template_id": template_id})
    await db["omr_templates"].delete_one({"_id": ObjectId(template_id)})


# ── Submissions ─────────────────────────────────────────────────────────────
@router.post("/submissions/single", response_model=OMRSubmissionOut)
async def upload_single_sheet(
    background_tasks: BackgroundTasks,
    template_id: str = Form(...),
    file: UploadFile = File(...),
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student uploads their single filled OMR sheet."""
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template_id")

    template = await db["omr_templates"].find_one({"_id": ObjectId(template_id)})
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    enrollment = await _verify_enrolled(db, template["class_id"], current_student["id"])

    if template.get("deadline") and datetime.utcnow() > template["deadline"]:
        raise HTTPException(status_code=403, detail="Deadline has passed")

    # Block duplicate submission
    existing = await db["omr_submissions"].find_one({
        "template_id": template_id,
        "submitter_id": current_student["id"],
        "submitter_role": "student",
    })
    if existing:
        raise HTTPException(status_code=409, detail="You have already submitted this OMR sheet. Re-uploads are not allowed.")

    if file.content_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type")

    record = {
        "template_id": template_id,
        "class_id": template["class_id"],
        "submitter_id": current_student["id"],
        "submitter_role": "student",
        "candidate_label": current_student.get("name"),
        "student_id_number": enrollment.get("student_id_number"),
        "original_name": file.filename,
        "total_marks": template["total_marks"],
        "status": "pending",
        "created_at": datetime.utcnow(),
    }
    result = await db["omr_submissions"].insert_one(record)
    sub_id = str(result.inserted_id)

    # Save file
    folder = UPLOAD_DIR / "omr" / sub_id
    folder.mkdir(parents=True, exist_ok=True)
    extension = os.path.splitext(file.filename)[1] or ".png"
    save_path = folder / f"sheet{extension}"

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception:
        await db["omr_submissions"].delete_one({"_id": result.inserted_id})
        raise HTTPException(status_code=500, detail="Storage failed")
    finally:
        file.file.close()

    str_save_path = relative_upload_path(save_path)
    await db["omr_submissions"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"sheet_image_path": str_save_path}},
    )
    record["sheet_image_path"] = str_save_path
    record["_id"] = result.inserted_id

    # Notify teacher
    await notify_user(
        db,
        user_id=template["teacher_id"],
        title="OMR sheet submitted",
        body=f"{current_student.get('name', 'A student')} submitted '{template.get('title', 'OMR')}'",
        link="/",
        category="omr",
    )

    background_tasks.add_task(process_omr_sheet, db, sub_id, str_save_path, template)
    return _map_submission(record)


@router.post("/submissions/batch")
async def upload_batch_sheets(
    background_tasks: BackgroundTasks,
    template_id: str = Form(...),
    files: List[UploadFile] = File(...),
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher batch-uploads many filled OMR sheets at once.
    Each file becomes one submission, processed in the background.
    """
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template_id")

    template = await db["omr_templates"].find_one({
        "_id": ObjectId(template_id), "teacher_id": current_teacher["id"]
    })
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    if not files:
        raise HTTPException(status_code=400, detail="No files provided")

    created_ids = []
    skipped = []

    for file in files:
        if file.content_type not in ALLOWED_TYPES:
            skipped.append({"name": file.filename, "reason": "Unsupported type"})
            continue

        # Use filename (without extension) as candidate label
        label = os.path.splitext(file.filename or "Sheet")[0]

        record = {
            "template_id": template_id,
            "class_id": template["class_id"],
            "submitter_id": None,
            "submitter_role": "teacher_batch",
            "candidate_label": label,
            "original_name": file.filename,
            "total_marks": template["total_marks"],
            "status": "pending",
            "created_at": datetime.utcnow(),
        }
        result = await db["omr_submissions"].insert_one(record)
        sub_id = str(result.inserted_id)

        folder = UPLOAD_DIR / "omr" / sub_id
        folder.mkdir(parents=True, exist_ok=True)
        extension = os.path.splitext(file.filename or "")[1] or ".png"
        save_path = folder / f"sheet{extension}"

        try:
            with save_path.open("wb") as buffer:
                shutil.copyfileobj(file.file, buffer)
        except Exception:
            await db["omr_submissions"].delete_one({"_id": result.inserted_id})
            skipped.append({"name": file.filename, "reason": "Storage failed"})
            continue
        finally:
            file.file.close()

        str_save_path = relative_upload_path(save_path)
        await db["omr_submissions"].update_one(
            {"_id": result.inserted_id},
            {"$set": {"sheet_image_path": str_save_path}},
        )

        background_tasks.add_task(process_omr_sheet, db, sub_id, str_save_path, template)
        created_ids.append(sub_id)

    return {
        "created": len(created_ids),
        "skipped": skipped,
        "submission_ids": created_ids,
    }


@router.get("/submissions/template/{template_id}", response_model=List[OMRSubmissionOut])
async def list_template_submissions(
    template_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher: list all submissions for an OMR template."""
    if not ObjectId.is_valid(template_id):
        raise HTTPException(status_code=400, detail="Invalid template_id")

    template = await db["omr_templates"].find_one({
        "_id": ObjectId(template_id), "teacher_id": current_teacher["id"]
    })
    if not template:
        raise HTTPException(status_code=404, detail="Template not found")

    cursor = db["omr_submissions"].find({"template_id": template_id}).sort("created_at", -1)
    subs = await cursor.to_list(length=1000)

    # Resolve student names
    student_ids = [s["submitter_id"] for s in subs if s.get("submitter_id")]
    valid_oids = [ObjectId(s) for s in student_ids if ObjectId.is_valid(s)]
    name_map = {}
    if valid_oids:
        users = await db["users"].find({"_id": {"$in": valid_oids}}).to_list(length=500)
        name_map = {str(u["_id"]): u.get("name", "Unknown") for u in users}

    out = []
    for s in subs:
        mapped = _map_submission(s)
        mapped["template_title"] = template.get("title")
        if s.get("submitter_id"):
            mapped["submitter_name"] = name_map.get(s["submitter_id"], s.get("candidate_label"))
        else:
            mapped["submitter_name"] = s.get("candidate_label")
        out.append(mapped)
    return out


@router.get("/submissions/me", response_model=List[OMRSubmissionOut])
async def list_my_omr_submissions(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student: list their own OMR submissions."""
    cursor = db["omr_submissions"].find({
        "submitter_id": current_student["id"],
        "submitter_role": "student",
    }).sort("created_at", -1)
    subs = await cursor.to_list(length=200)

    # Attach template titles
    template_ids = list({s["template_id"] for s in subs if s.get("template_id")})
    valid_oids = [ObjectId(t) for t in template_ids if ObjectId.is_valid(t)]
    title_map = {}
    if valid_oids:
        templates = await db["omr_templates"].find({"_id": {"$in": valid_oids}}).to_list(length=500)
        title_map = {str(t["_id"]): t.get("title", "OMR") for t in templates}

    out = []
    for s in subs:
        mapped = _map_submission(s)
        mapped["template_title"] = title_map.get(s["template_id"])
        mapped["submitter_name"] = current_student.get("name")
        out.append(mapped)
    return out


@router.delete("/submissions/{submission_id}", status_code=204)
async def delete_submission(
    submission_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher: delete an OMR submission (e.g. wrong batch upload)."""
    if not ObjectId.is_valid(submission_id):
        raise HTTPException(status_code=400, detail="Invalid submission_id")
    sub = await db["omr_submissions"].find_one({"_id": ObjectId(submission_id)})
    if not sub:
        raise HTTPException(status_code=404, detail="Submission not found")
    template = await db["omr_templates"].find_one({"_id": ObjectId(sub["template_id"])}) if ObjectId.is_valid(sub["template_id"]) else None
    if not template or template.get("teacher_id") != current_teacher["id"]:
        raise HTTPException(status_code=403, detail="Not authorized")
    await db["omr_submissions"].delete_one({"_id": ObjectId(submission_id)})
