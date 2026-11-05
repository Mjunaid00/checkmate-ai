"""
Messages Router — students and teachers exchange messages.

Three scopes:
- submission_id : conversation about a specific submission
- assignment_id : student → teacher about a generic assignment
- class_id      : class-wide chat (student ↔ teacher), persists beyond deadlines

Teachers can reply to class-scoped threads to a specific student via to_user_id.
"""
from datetime import datetime
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from bson import ObjectId

from database import get_db
from routers.deps import get_current_user, get_current_teacher
from services.notifications import notify_user

router = APIRouter(prefix="/messages", tags=["messages"])


class MessageCreate(BaseModel):
    text: str
    submission_id: Optional[str] = None
    assignment_id: Optional[str] = None
    class_id: Optional[str] = None
    # Used by teachers replying on a class-scoped thread to a specific student
    to_user_id: Optional[str] = None


def _map(doc: dict) -> dict:
    doc["message_id"] = str(doc["_id"])
    doc.pop("_id", None)
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


async def _resolve_recipient(db, current_user: dict, body: MessageCreate) -> tuple:
    """
    Determine the recipient and class context for a message.
    Returns: (recipient_user_id, class_id, context_label, student_id_number_or_none)
    """
    # ── Submission-scoped ───────────────────────────────────────
    if body.submission_id:
        if not ObjectId.is_valid(body.submission_id):
            raise HTTPException(status_code=400, detail="Invalid submission_id")
        sub = await db["submissions"].find_one({"_id": ObjectId(body.submission_id)})
        if not sub:
            raise HTTPException(status_code=404, detail="Submission not found")
        assignment = await db["assignments"].find_one({"_id": ObjectId(sub["assignment_id"])})
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")

        if current_user["role"] == "student":
            if sub["student_id"] != current_user["id"]:
                raise HTTPException(status_code=403, detail="Not your submission")
            return assignment["teacher_id"], assignment["class_id"], assignment.get("title", ""), sub.get("student_id_number")

        # Teacher reply on submission
        if assignment["teacher_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your assignment")
        return sub["student_id"], assignment["class_id"], assignment.get("title", ""), sub.get("student_id_number")

    # ── Assignment-scoped (student-only) ────────────────────────
    if body.assignment_id:
        if not ObjectId.is_valid(body.assignment_id):
            raise HTTPException(status_code=400, detail="Invalid assignment_id")
        assignment = await db["assignments"].find_one({"_id": ObjectId(body.assignment_id)})
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        if current_user["role"] == "student":
            enr = await db["enrollments"].find_one({
                "class_id": assignment["class_id"], "student_id": current_user["id"]
            })
            return assignment["teacher_id"], assignment["class_id"], assignment.get("title", ""), (enr or {}).get("student_id_number")
        raise HTTPException(status_code=400, detail="Teachers must reply via submission_id or class_id+to_user_id")

    # ── Class-scoped ────────────────────────────────────────────
    if body.class_id:
        if not ObjectId.is_valid(body.class_id):
            raise HTTPException(status_code=400, detail="Invalid class_id")
        cls = await db["classes"].find_one({"_id": ObjectId(body.class_id)})
        if not cls:
            raise HTTPException(status_code=404, detail="Class not found")

        if current_user["role"] == "student":
            # Student must be enrolled
            enr = await db["enrollments"].find_one({
                "class_id": body.class_id, "student_id": current_user["id"]
            })
            if not enr:
                raise HTTPException(status_code=403, detail="Enroll in this class to message the teacher")
            return cls["teacher_id"], body.class_id, cls.get("name", ""), enr.get("student_id_number")

        # Teacher replying on class-scoped thread → must specify which student
        if cls["teacher_id"] != current_user["id"]:
            raise HTTPException(status_code=403, detail="Not your class")
        if not body.to_user_id:
            raise HTTPException(status_code=400, detail="Teachers must specify to_user_id when replying on a class thread")
        # Verify the target student is enrolled
        target_enr = await db["enrollments"].find_one({
            "class_id": body.class_id, "student_id": body.to_user_id
        })
        if not target_enr:
            raise HTTPException(status_code=404, detail="That student is not enrolled in this class")
        return body.to_user_id, body.class_id, cls.get("name", ""), target_enr.get("student_id_number")

    raise HTTPException(status_code=400, detail="Must specify submission_id, assignment_id, or class_id")


@router.post("/")
async def send_message(
    body: MessageCreate,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Send a message in any scope. Class messaging persists beyond deadlines."""
    text = body.text.strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")
    if len(text) > 2000:
        raise HTTPException(status_code=400, detail="Message too long (max 2000 chars)")

    recipient_id, class_id, context_label, student_id_number = await _resolve_recipient(db, current_user, body)

    # If the sender is a student, snapshot their academic ID on the message
    sender_student_id_number = None
    if current_user["role"] == "student":
        sender_student_id_number = student_id_number

    record = {
        "from_user_id": current_user["id"],
        "from_name": current_user.get("name", "Unknown"),
        "from_role": current_user["role"],
        "from_student_id_number": sender_student_id_number,
        "to_user_id": recipient_id,
        "submission_id": body.submission_id,
        "assignment_id": body.assignment_id,
        "class_id": class_id,
        "text": text,
        "read": False,
        "created_at": datetime.utcnow(),
    }
    result = await db["messages"].insert_one(record)
    record["_id"] = result.inserted_id

    sender_name = current_user.get("name", "Someone")
    title = "New message" if current_user["role"] == "student" else "Reply from teacher"
    snippet = text[:80] + ("..." if len(text) > 80 else "")
    sender_label = f"{sender_name}{f' ({sender_student_id_number})' if sender_student_id_number else ''}"
    await notify_user(
        db,
        user_id=recipient_id,
        title=title,
        body=f"{sender_label}: {snippet}",
        link="/",
        category="message",
    )

    return _map(record)


@router.get("/")
async def list_my_messages(
    submission_id: Optional[str] = None,
    class_id: Optional[str] = None,
    other_user_id: Optional[str] = None,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """
    List messages involving the current user.

    Filters:
    - submission_id : only messages tied to a specific submission
    - class_id      : class-scoped thread (no submission_id, no assignment_id)
    - other_user_id : messages between current user and a specific other user
    """
    base: dict = {
        "$or": [
            {"from_user_id": current_user["id"]},
            {"to_user_id": current_user["id"]},
        ]
    }
    extra_filters = []

    if submission_id:
        extra_filters.append({"submission_id": submission_id})
    if class_id:
        # Class-scoped means tied to class_id with no submission/assignment context
        extra_filters.append({
            "class_id": class_id,
            "submission_id": None,
            "assignment_id": None,
        })
    if other_user_id:
        extra_filters.append({
            "$or": [
                {"from_user_id": other_user_id},
                {"to_user_id": other_user_id},
            ]
        })

    if extra_filters:
        query = {"$and": [base] + extra_filters}
    else:
        query = base

    cursor = db["messages"].find(query).sort("created_at", 1)
    results = await cursor.to_list(length=500)
    return [_map(m) for m in results]


@router.get("/threads")
async def list_threads(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List unique conversation threads for the current user."""
    cursor = db["messages"].find({
        "$or": [
            {"from_user_id": current_user["id"]},
            {"to_user_id": current_user["id"]},
        ]
    }).sort("created_at", -1)
    messages = await cursor.to_list(length=2000)

    threads = {}
    for m in messages:
        other_id = m["to_user_id"] if m["from_user_id"] == current_user["id"] else m["from_user_id"]
        thread_key = (m.get("submission_id") or m.get("class_id") or "general", other_id)

        if thread_key not in threads:
            other_name = m["from_name"] if m["from_user_id"] == other_id else None
            if not other_name:
                if ObjectId.is_valid(other_id):
                    user_doc = await db["users"].find_one({"_id": ObjectId(other_id)})
                    other_name = user_doc.get("name", "Unknown") if user_doc else "Unknown"
                else:
                    other_name = "Unknown"

            threads[thread_key] = {
                "submission_id": m.get("submission_id"),
                "class_id": m.get("class_id"),
                "assignment_id": m.get("assignment_id"),
                "other_user_id": other_id,
                "other_user_name": other_name,
                "other_student_id_number": m.get("from_student_id_number") if m["from_user_id"] == other_id else None,
                "last_message": m["text"][:100],
                "last_message_at": m["created_at"].isoformat(),
                "unread_count": 0,
            }

        if m["to_user_id"] == current_user["id"] and not m.get("read"):
            threads[thread_key]["unread_count"] += 1

    return list(threads.values())


@router.get("/class/{class_id}/threads")
async def class_threads(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Teacher: list one thread per enrolled student for a class.
    Includes students with no messages yet so the teacher can initiate.
    """
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    cls = await db["classes"].find_one({
        "_id": ObjectId(class_id), "teacher_id": current_teacher["id"]
    })
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")

    enrollments = await db["enrollments"].find({"class_id": class_id}).to_list(length=500)
    student_ids = [e["student_id"] for e in enrollments]
    valid_oids = [ObjectId(s) for s in student_ids if ObjectId.is_valid(s)]
    user_map = {}
    if valid_oids:
        users = await db["users"].find({"_id": {"$in": valid_oids}}).to_list(length=500)
        user_map = {str(u["_id"]): u for u in users}

    enrollment_map = {e["student_id"]: e for e in enrollments}

    threads = []
    for sid in student_ids:
        # Pull all class-scoped messages between this student and the teacher
        msgs = await db["messages"].find({
            "class_id": class_id,
            "submission_id": None,
            "assignment_id": None,
            "$or": [
                {"from_user_id": sid, "to_user_id": current_teacher["id"]},
                {"from_user_id": current_teacher["id"], "to_user_id": sid},
            ],
        }).sort("created_at", -1).to_list(length=200)

        last = msgs[0] if msgs else None
        unread = sum(
            1 for m in msgs
            if m.get("to_user_id") == current_teacher["id"] and not m.get("read")
        )

        user = user_map.get(sid, {})
        threads.append({
            "class_id": class_id,
            "student_id": sid,
            "student_name": user.get("name", "Unknown"),
            "student_email": user.get("email"),
            "student_id_number": enrollment_map.get(sid, {}).get("student_id_number"),
            "message_count": len(msgs),
            "unread_count": unread,
            "last_message": last["text"][:100] if last else None,
            "last_message_at": last["created_at"].isoformat() if last else None,
            "last_message_from_role": last["from_role"] if last else None,
        })

    # Sort: threads with messages first (by recency), then no-message students alphabetically
    threads.sort(key=lambda t: (
        t["last_message_at"] is None,
        -(datetime.fromisoformat(t["last_message_at"]).timestamp() if t["last_message_at"] else 0),
        t["student_name"] or "",
    ))
    return {
        "class_id": class_id,
        "class_name": cls.get("name", ""),
        "threads": threads,
    }


@router.patch("/{message_id}/read")
async def mark_read(
    message_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mark a message as read (only the recipient can)."""
    if not ObjectId.is_valid(message_id):
        raise HTTPException(status_code=400, detail="Invalid message_id")
    result = await db["messages"].update_one(
        {"_id": ObjectId(message_id), "to_user_id": current_user["id"]},
        {"$set": {"read": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Message not found")
    return {"detail": "marked as read"}
