from fastapi import APIRouter, Depends, HTTPException, Body
from typing import List, Optional
from datetime import datetime
from bson import ObjectId
from pydantic import BaseModel
from database import get_db
from models.school import ClassGroupOut
from routers.deps import get_current_teacher, get_current_user

router = APIRouter(prefix="/classes", tags=["classes"])


def map_class(doc: dict) -> dict:
    doc["class_id"] = str(doc["_id"])
    return doc


async def _attach_counts(db, classes: List[dict]) -> None:
    """Attach enrollment_count and assignments_count to each class doc."""
    for c in classes:
        c["enrollment_count"] = await db["enrollments"].count_documents({"class_id": c["class_id"]})
        c["assignments_count"] = await db["assignments"].count_documents({"class_id": c["class_id"]})


class ClassCreateBody(BaseModel):
    name: str
    max_students: Optional[int] = None


class ClassUpdateBody(BaseModel):
    name: Optional[str] = None
    max_students: Optional[int] = None


@router.post("/", response_model=ClassGroupOut)
async def create_class(
    body: ClassCreateBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher creates a new Class Group with optional student cap."""
    if not body.name or not body.name.strip():
        raise HTTPException(status_code=400, detail="Class name is required")
    if body.max_students is not None and body.max_students < 1:
        raise HTTPException(status_code=400, detail="max_students must be at least 1")

    class_doc = {
        "name": body.name.strip(),
        "teacher_id": current_teacher["id"],
        "max_students": body.max_students,
        "created_at": datetime.utcnow(),
    }
    result = await db["classes"].insert_one(class_doc)
    class_doc["_id"] = result.inserted_id
    mapped = map_class(class_doc)
    mapped["enrollment_count"] = 0
    mapped["assignments_count"] = 0
    return mapped


@router.get("/", response_model=List[ClassGroupOut])
async def list_classes(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List classes. Teachers see their own; students see all with enrollment status."""
    query = {}
    if current_user["role"] in ("teacher", "admin"):  # admins act as teachers of their own classes
        query = {"teacher_id": current_user["id"]}

    cursor = db["classes"].find(query).sort("created_at", -1)
    classes = await cursor.to_list(length=100)
    result = [map_class(c) for c in classes]

    await _attach_counts(db, result)

    if current_user["role"] == "student":
        enrolled_cursor = db["enrollments"].find({"student_id": current_user["id"]})
        enrolled_docs = await enrolled_cursor.to_list(length=200)
        enrolled_ids = {e["class_id"] for e in enrolled_docs}
        for c in result:
            c["enrolled"] = c["class_id"] in enrolled_ids

    return result


@router.patch("/{class_id}", response_model=ClassGroupOut)
async def update_class(
    class_id: str,
    body: ClassUpdateBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher updates class name and/or student cap."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    updates = {}
    if body.name is not None:
        if not body.name.strip():
            raise HTTPException(status_code=400, detail="Class name cannot be empty")
        updates["name"] = body.name.strip()
    if body.max_students is not None:
        if body.max_students < 1:
            raise HTTPException(status_code=400, detail="max_students must be at least 1")
        # Don't allow lowering cap below current enrollment
        current = await db["enrollments"].count_documents({"class_id": class_id})
        if body.max_students < current:
            raise HTTPException(
                status_code=400,
                detail=f"Cannot set max_students to {body.max_students}; {current} students already enrolled",
            )
        updates["max_students"] = body.max_students

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    result = await db["classes"].update_one(
        {"_id": ObjectId(class_id), "teacher_id": current_teacher["id"]},
        {"$set": updates},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Class not found")

    updated = await db["classes"].find_one({"_id": ObjectId(class_id)})
    mapped = map_class(updated)
    await _attach_counts(db, [mapped])
    return mapped


@router.delete("/{class_id}", status_code=204)
async def delete_class(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher deletes a class and cascades all related records."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    class_group = await db["classes"].find_one(
        {"_id": ObjectId(class_id), "teacher_id": current_teacher["id"]}
    )
    if not class_group:
        raise HTTPException(status_code=404, detail="Class not found")

    assignments = await db["assignments"].find({"class_id": class_id}).to_list(length=None)
    assignment_ids = [str(a["_id"]) for a in assignments]
    if assignment_ids:
        await db["submissions"].delete_many({"assignment_id": {"$in": assignment_ids}})

    await db["assignments"].delete_many({"class_id": class_id})
    await db["enrollments"].delete_many({"class_id": class_id})
    await db["classes"].delete_one({"_id": ObjectId(class_id)})
