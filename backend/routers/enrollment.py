from fastapi import APIRouter, Depends, HTTPException, Body
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
from database import get_db
from models.school import EnrollmentOut
from routers.deps import get_current_student

router = APIRouter(prefix="/enrollment", tags=["enrollment"])


class EnrollBody(BaseModel):
    student_id_number: str


@router.post("/{class_id}", response_model=EnrollmentOut)
async def enroll_in_class(
    class_id: str,
    body: EnrollBody,
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student enrolls in a class group with their academic student ID."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    student_id_number = body.student_id_number.strip()
    if not student_id_number:
        raise HTTPException(status_code=400, detail="Student ID is required to enroll")

    class_group = await db["classes"].find_one({"_id": ObjectId(class_id)})
    if not class_group:
        raise HTTPException(status_code=404, detail="Class not found")

    existing = await db["enrollments"].find_one(
        {"class_id": class_id, "student_id": current_student["id"]}
    )
    if existing:
        raise HTTPException(status_code=409, detail="Already enrolled in this class")

    # Check student capacity if defined
    max_students = class_group.get("max_students")
    if max_students is not None:
        current_count = await db["enrollments"].count_documents({"class_id": class_id})
        if current_count >= max_students:
            raise HTTPException(
                status_code=403,
                detail=f"Class is full ({current_count}/{max_students} enrolled)",
            )

    record = {
        "class_id": class_id,
        "student_id": current_student["id"],
        "student_id_number": student_id_number,
        "enrolled_at": datetime.utcnow(),
    }
    await db["enrollments"].insert_one(record)

    # Notify teacher
    from services.notifications import notify_user
    await notify_user(
        db,
        user_id=class_group["teacher_id"],
        title="New student enrolled",
        body=f"{current_student.get('name', 'A student')} (ID: {student_id_number}) enrolled in {class_group.get('name', 'a class')}",
        link=f"/",
        category="enrollment",
    )

    return record


@router.delete("/{class_id}", status_code=204)
async def unenroll_from_class(
    class_id: str,
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student leaves a class group."""
    result = await db["enrollments"].delete_one(
        {"class_id": class_id, "student_id": current_student["id"]}
    )
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Not enrolled in this class")


@router.get("/my", response_model=list[EnrollmentOut])
async def my_enrollments(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """List all classes the student is enrolled in."""
    cursor = db["enrollments"].find({"student_id": current_student["id"]})
    results = await cursor.to_list(length=200)
    return results
