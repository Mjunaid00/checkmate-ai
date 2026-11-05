from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Form, BackgroundTasks

import os
import shutil
from datetime import datetime
from pathlib import Path
from typing import Literal

from database import get_db
from models.exam import ExamInDB, ExamOut
from routers.deps import get_current_teacher
from services.grading import process_exam_background

router = APIRouter(prefix="/upload", tags=["upload"])

# Base upload directory from environment (relative to backend/)
UPLOAD_DIR = Path(os.getenv("UPLOAD_DIR", "../uploads"))

@router.get("/ping")
async def upload_ping():
    """Health-check — confirms the upload router is mounted."""
    return {"router": "upload", "status": "ok"}


@router.post("/exam", response_model=ExamOut)
async def upload_exam(
    background_tasks: BackgroundTasks,
    exam_title:  str = Form(...),
    total_marks: int = Form(...),
    file: UploadFile = File(...),
    current_teacher: dict = Depends(get_current_teacher),
    db = Depends(get_db)
):
    """
    Teacher-only endpoint to upload a new exam (PDF or Image).
    Saves file to filesystem and metadata to MongoDB.
    """
    # 1. Basic validation (file types)
    allowed_types = ["application/pdf", "image/jpeg", "image/png"]
    if file.content_type not in allowed_types:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unsupported file type: {file.content_type}. Use PDF, JPEG, or PNG."
        )

    # 2. Prepare initial DB record to get an ID
    exam_record = {
        "exam_title":    exam_title,
        "total_marks":   total_marks,
        "teacher_id":    current_teacher["id"],
        "original_name": file.filename,
        "file_type":     file.content_type,
        "status":        "uploaded",
        "created_at":    datetime.utcnow()
    }
    
    # Insert to get MongoDB _id
    result = await db["exams"].insert_one(exam_record)
    exam_id = str(result.inserted_id)

    # 3. Create filesystem path
    # Path: uploads/{exam_id}/original.{ext}
    extension = os.path.splitext(file.filename)[1]
    exam_folder = UPLOAD_DIR / exam_id
    exam_folder.mkdir(parents=True, exist_ok=True)
    
    file_save_path = exam_folder / f"original{extension}"
    
    # 4. Save file to disk
    try:
        with file_save_path.open("wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        file_size = os.path.getsize(file_save_path)
    except Exception as e:
        # Cleanup DB record if file save fails
        await db["exams"].delete_one({"_id": result.inserted_id})
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"File storage failed: {str(e)}"
        )
    finally:
        file.file.close()

    # 5. Update DB record with file details
    await db["exams"].update_one(
        {"_id": result.inserted_id},
        {"$set": {
            "file_path": str(file_save_path.relative_to(UPLOAD_DIR.parent)),
            "file_size": file_size
        }}
    )

    # Dispatch background grading task
    background_tasks.add_task(process_exam_background, exam_id, file_save_path, total_marks)

    # 6. Return response
    return {
        "exam_id":       exam_id,
        "exam_title":    exam_title,
        "total_marks":   total_marks,
        "teacher_id":    current_teacher["id"],
        "original_name": file.filename,
        "status":        "uploaded",
        "created_at":    exam_record["created_at"]
    }
