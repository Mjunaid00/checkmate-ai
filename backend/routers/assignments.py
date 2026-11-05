from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form
from typing import Optional
import os
import shutil
from datetime import datetime
from pathlib import Path
from bson import ObjectId

from config import UPLOAD_DIR, relative_upload_path
from core.timeutil import parse_deadline
from database import get_db
from models.school import AssignmentInDB, AssignmentOut
from routers.deps import get_current_teacher, get_current_user

router = APIRouter(prefix="/assignments", tags=["assignments"])

def map_assignment(doc: dict) -> dict:
    doc["assignment_id"] = str(doc["_id"])
    return doc

@router.post("/", response_model=AssignmentOut)
async def upload_assignment(
    class_id: str = Form(...),
    title: str = Form(...),
    total_marks: int = Form(...),
    grading_prompt: str = Form(""),
    deadline: Optional[str] = Form(None),
    plagiarism_check: bool = Form(False),
    allowed_formats: Optional[str] = Form(None),  # Comma-separated: "pdf,png,jpg"
    file: UploadFile = File(...),
    current_teacher: dict = Depends(get_current_teacher),
    db = Depends(get_db)
):
    """Teacher uploads an assignment question paper/rubric with optional grading prompt."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    class_group = await db["classes"].find_one({"_id": ObjectId(class_id), "teacher_id": current_teacher["id"]})
    if not class_group:
        raise HTTPException(status_code=404, detail="Class Group not found")

    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(status_code=400, detail="Unsupported file type.")

    # Parse deadline if provided
    parsed_deadline = None
    if deadline and deadline.strip():
        try:
            parsed_deadline = parse_deadline(deadline)
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid deadline format. Use ISO format (YYYY-MM-DDTHH:MM)")
        if parsed_deadline < datetime.utcnow():
            raise HTTPException(status_code=400, detail="Deadline cannot be in the past")

    # Parse allowed formats list (used to validate student submissions)
    parsed_formats = None
    if allowed_formats and allowed_formats.strip():
        parsed_formats = [f.strip().lower().lstrip(".") for f in allowed_formats.split(",") if f.strip()]
        valid_formats = {"pdf", "png", "jpg", "jpeg"}
        for fmt in parsed_formats:
            if fmt not in valid_formats:
                raise HTTPException(status_code=400, detail=f"Unsupported format: {fmt}. Use pdf, png, jpg")

    # Db Insert
    record = {
        "class_id": class_id,
        "teacher_id": current_teacher["id"],
        "title": title,
        "total_marks": total_marks,
        "grading_prompt": grading_prompt if grading_prompt.strip() else None,
        "deadline": parsed_deadline,
        "plagiarism_check": plagiarism_check,
        "allowed_formats": parsed_formats,
        "original_name": file.filename,
        "file_type": file.content_type,
        "created_at": datetime.utcnow()
    }
    result = await db["assignments"].insert_one(record)
    assignment_id = str(result.inserted_id)

    # Save logic
    folder = UPLOAD_DIR / "assignments" / assignment_id
    folder.mkdir(parents=True, exist_ok=True)
    extension = os.path.splitext(file.filename)[1]
    save_path = folder / f"rubric{extension}"

    try:
        with save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        await db["assignments"].delete_one({"_id": result.inserted_id})
        raise HTTPException(status_code=500, detail="Storage failed")
    finally:
        file.file.close()

    await db["assignments"].update_one(
        {"_id": result.inserted_id},
        {"$set": {"rubric_file_path": relative_upload_path(save_path)}}
    )

    # Notify enrolled students about new assignment
    from services.notifications import notify_user
    enrolled = await db["enrollments"].find({"class_id": class_id}).to_list(length=500)
    for enr in enrolled:
        await notify_user(
            db,
            user_id=enr["student_id"],
            title="New assignment posted",
            body=f"'{title}' was added to {class_group.get('name', 'your class')}",
            link="/",
            category="assignment",
        )

    record["_id"] = result.inserted_id
    return map_assignment(record)

@router.patch("/{assignment_id}", response_model=AssignmentOut)
async def update_assignment(
    assignment_id: str,
    title: Optional[str] = None,
    total_marks: Optional[int] = None,
    grading_prompt: Optional[str] = None,
    deadline: Optional[str] = None,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher edits an assignment's title, marks, grading prompt, or deadline."""
    if not ObjectId.is_valid(assignment_id):
        raise HTTPException(status_code=400, detail="Invalid assignment_id")

    assignment = await db["assignments"].find_one({
        "_id": ObjectId(assignment_id), "teacher_id": current_teacher["id"]
    })
    if not assignment:
        raise HTTPException(status_code=404, detail="Assignment not found")

    updates = {}
    if title is not None and title.strip():
        updates["title"] = title.strip()
    if total_marks is not None:
        updates["total_marks"] = total_marks
    if grading_prompt is not None:
        updates["grading_prompt"] = grading_prompt.strip() if grading_prompt.strip() else None
    if deadline is not None:
        if deadline.strip() == "" or deadline.strip().lower() == "none":
            updates["deadline"] = None
        else:
            try:
                new_deadline = parse_deadline(deadline)
            except ValueError:
                raise HTTPException(status_code=400, detail="Invalid deadline format")
            # Only reject past deadlines if it's a genuine change.
            original = assignment.get("deadline")
            if new_deadline != original and new_deadline < datetime.utcnow():
                raise HTTPException(status_code=400, detail="Deadline cannot be in the past")
            updates["deadline"] = new_deadline

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db["assignments"].update_one(
        {"_id": ObjectId(assignment_id)},
        {"$set": updates},
    )
    updated = await db["assignments"].find_one({"_id": ObjectId(assignment_id)})
    return map_assignment(updated)


@router.get("/class/{class_id}", response_model=list[AssignmentOut])
async def list_assignments(
    class_id: str,
    current_user: dict = Depends(get_current_user),
    db = Depends(get_db)
):
    """List assignments for a class. Students must be enrolled to view."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    # Students must be enrolled to see assignments
    if current_user["role"] == "student":
        enrollment = await db["enrollments"].find_one({
            "class_id": class_id,
            "student_id": current_user["id"]
        })
        if not enrollment:
            raise HTTPException(status_code=403, detail="Enroll in this class to view assignments")

    cursor = db["assignments"].find({"class_id": class_id}).sort("created_at", -1)
    results = await cursor.to_list(length=100)
    return [map_assignment(a) for a in results]
