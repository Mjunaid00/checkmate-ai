"""
Admin router — user account management for admins.

Endpoints:
  GET    /admin/users               list all accounts
  POST   /admin/users               create a new account (any role)
  PATCH  /admin/users/{id}          update name / role / institution / active flag
  POST   /admin/users/{id}/password reset password
  DELETE /admin/users/{id}          delete the account (and owned data)
  GET    /admin/stats               quick counts for the admin dashboard

Bootstrap: if no admin exists at startup and ADMIN_EMAIL / ADMIN_PASSWORD env
vars are set, one is created automatically.
"""
import os
from datetime import datetime
from typing import List, Optional, Literal

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field
from bson import ObjectId

from database import get_db
from core.security import hash_password
from routers.auth import _validate_name
from routers.deps import get_current_admin
from services.audit import record_audit

router = APIRouter(prefix="/admin", tags=["admin"])


# ── Bodies ──────────────────────────────────────────────────────────────────

class AdminUserCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=80)
    email: EmailStr
    password: str = Field(..., min_length=6)
    role: Literal["student", "teacher", "admin"] = "student"


class AdminUserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=80)
    email: Optional[EmailStr] = None
    role: Optional[Literal["student", "teacher", "admin"]] = None
    institution: Optional[str] = None
    is_active: Optional[bool] = None


class AdminPasswordReset(BaseModel):
    new_password: str = Field(..., min_length=6)


# ── Helpers ─────────────────────────────────────────────────────────────────

def _to_admin_user_out(u: dict) -> dict:
    return {
        "id": str(u["_id"]),
        "name": u.get("name", ""),
        "email": u.get("email", ""),
        "role": u.get("role", "student"),
        "institution": u.get("institution"),
        "phone": u.get("phone"),
        "is_active": u.get("is_active", True),
        "created_at": u.get("created_at"),
    }


# ── Bootstrap helper (called from main.py startup) ──────────────────────────

async def ensure_admin_bootstrap(db) -> None:
    """
    If no admin exists and ADMIN_EMAIL / ADMIN_PASSWORD are configured,
    create the first admin. Safe to call repeatedly.
    """
    if db is None:
        return
    try:
        any_admin = await db["users"].find_one({"role": "admin"})
        if any_admin:
            return
    except Exception:
        return

    email = (os.getenv("ADMIN_EMAIL") or "").strip()
    password = os.getenv("ADMIN_PASSWORD") or ""
    name = (os.getenv("ADMIN_NAME") or "Admin").strip()
    if not email or len(password) < 6:
        # Fallback for local dev only — surfaced in the server logs so the
        # operator can immediately change it.
        email = "admin@checkmate.ai"
        password = "admin123"
        print(
            "[admin-bootstrap] Created default admin admin@checkmate.ai / admin123 — "
            "set ADMIN_EMAIL / ADMIN_PASSWORD env vars to override and CHANGE THIS PASSWORD."
        )

    # Don't clobber an existing user that happens to share the email
    existing = await db["users"].find_one({"email": email})
    if existing:
        await db["users"].update_one(
            {"_id": existing["_id"]},
            {"$set": {"role": "admin", "is_active": True}},
        )
        print(f"[admin-bootstrap] Promoted existing user {email} to admin.")
        return

    await db["users"].insert_one({
        "name": name,
        "email": email,
        "hashed_password": hash_password(password),
        "role": "admin",
        "created_at": datetime.utcnow(),
        "is_active": True,
    })
    print(f"[admin-bootstrap] Admin account created: {email}")


# ── Endpoints ───────────────────────────────────────────────────────────────

@router.get("/stats")
async def admin_stats(
    _admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    students = await db["users"].count_documents({"role": "student"})
    teachers = await db["users"].count_documents({"role": "teacher"})
    admins   = await db["users"].count_documents({"role": "admin"})
    total    = students + teachers + admins
    classes  = await db["classes"].count_documents({})
    assignments = await db["assignments"].count_documents({})
    quizzes = await db["quizzes"].count_documents({})
    return {
        "users": {"total": total, "students": students, "teachers": teachers, "admins": admins},
        "classes": classes,
        "assignments": assignments,
        "quizzes": quizzes,
    }


@router.get("/users")
async def list_users(
    role: Optional[str] = None,
    q: Optional[str] = None,
    _admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    """List every user account, optionally filtered by role or search term."""
    query: dict = {}
    if role and role in {"student", "teacher", "admin"}:
        query["role"] = role
    if q:
        query["$or"] = [
            {"name":  {"$regex": q, "$options": "i"}},
            {"email": {"$regex": q, "$options": "i"}},
        ]
    cursor = db["users"].find(query).sort("created_at", -1)
    users = await cursor.to_list(length=1000)
    return [_to_admin_user_out(u) for u in users]


@router.post("/users", status_code=201)
async def create_user(
    body: AdminUserCreate,
    _admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    existing = await db["users"].find_one({"email": body.email})
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    cleaned_name = _validate_name(body.name)
    record = {
        "name": cleaned_name,
        "email": body.email,
        "hashed_password": hash_password(body.password),
        "role": body.role,
        "created_at": datetime.utcnow(),
        "is_active": True,
    }
    result = await db["users"].insert_one(record)
    record["_id"] = result.inserted_id
    return _to_admin_user_out(record)


@router.patch("/users/{user_id}")
async def update_user(
    user_id: str,
    body: AdminUserUpdate,
    admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")

    target = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    updates = {}
    if body.name is not None:
        updates["name"] = _validate_name(body.name)
    if body.email is not None:
        new_email = body.email.strip().lower()
        if new_email != target.get("email"):
            taken = await db["users"].find_one({"email": new_email, "_id": {"$ne": target["_id"]}})
            if taken:
                raise HTTPException(status_code=409, detail="That email is already used by another account")
            updates["email"] = new_email
    if body.institution is not None:
        updates["institution"] = body.institution.strip()
    if body.is_active is not None:
        # Never let an admin lock themselves out.
        if str(target["_id"]) == admin["id"] and body.is_active is False:
            raise HTTPException(status_code=400, detail="You cannot deactivate your own account")
        updates["is_active"] = body.is_active
    if body.role is not None:
        # Don't allow removing the last admin.
        if target.get("role") == "admin" and body.role != "admin":
            remaining = await db["users"].count_documents({"role": "admin", "_id": {"$ne": target["_id"]}})
            if remaining == 0:
                raise HTTPException(status_code=400, detail="Cannot demote the last admin")
        updates["role"] = body.role

    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    await db["users"].update_one({"_id": target["_id"]}, {"$set": updates})
    updated = await db["users"].find_one({"_id": target["_id"]})
    await record_audit(
        db, admin, "user_updated", "user", user_id, None, require_reason=False,
        details={"email": target.get("email"), "changes": {k: {"from": target.get(k), "to": v} for k, v in updates.items()}},
    )
    return _to_admin_user_out(updated)


@router.post("/users/{user_id}/password")
async def reset_password(
    user_id: str,
    body: AdminPasswordReset,
    admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    target = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    await db["users"].update_one(
        {"_id": target["_id"]},
        {"$set": {"hashed_password": hash_password(body.new_password)}},
    )
    await record_audit(db, admin, "password_reset", "user", user_id, None, require_reason=False,
                       details={"email": target.get("email"), "role": target.get("role")})
    return {"detail": "Password reset successfully"}


@router.delete("/users/{user_id}", status_code=204)
async def delete_user(
    user_id: str,
    admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    if not ObjectId.is_valid(user_id):
        raise HTTPException(status_code=400, detail="Invalid user id")
    if user_id == admin["id"]:
        raise HTTPException(status_code=400, detail="You cannot delete your own account from here. Use the Settings page.")

    target = await db["users"].find_one({"_id": ObjectId(user_id)})
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.get("role") == "admin":
        remaining = await db["users"].count_documents({"role": "admin", "_id": {"$ne": target["_id"]}})
        if remaining == 0:
            raise HTTPException(status_code=400, detail="Cannot delete the last admin")

    sid = str(target["_id"])
    if target.get("role") == "teacher":
        assignments = await db["assignments"].find({"teacher_id": sid}).to_list(length=None)
        assignment_ids = [str(a["_id"]) for a in assignments]
        if assignment_ids:
            await db["submissions"].delete_many({"assignment_id": {"$in": assignment_ids}})
        await db["assignments"].delete_many({"teacher_id": sid})
        await db["classes"].delete_many({"teacher_id": sid})
    elif target.get("role") == "student":
        await db["submissions"].delete_many({"student_id": sid})
        await db["enrollments"].delete_many({"student_id": sid})

    await db["users"].delete_one({"_id": target["_id"]})
    await record_audit(db, admin, "user_deleted", "user", sid, None, require_reason=False,
                       details={"email": target.get("email"), "role": target.get("role"), "name": target.get("name")})


# ── Oversight: every class with its teacher and counts ──────────────────────

@router.get("/classes")
async def list_all_classes(
    _admin: dict = Depends(get_current_admin),
    db=Depends(get_db),
):
    """All classes in the system, with the owning teacher and counts, for the admin's class browser."""
    classes = await db["classes"].find({}).sort("created_at", -1).to_list(length=1000)
    teacher_ids = {c.get("teacher_id") for c in classes if c.get("teacher_id") and ObjectId.is_valid(c.get("teacher_id"))}
    teachers = {}
    if teacher_ids:
        async for u in db["users"].find({"_id": {"$in": [ObjectId(t) for t in teacher_ids]}}, {"name": 1, "email": 1}):
            teachers[str(u["_id"])] = u
    out = []
    for c in classes:
        cid = str(c["_id"])
        t = teachers.get(c.get("teacher_id"), {})
        out.append({
            "class_id": cid,
            "name": c.get("name", ""),
            "description": c.get("description"),
            "teacher_id": c.get("teacher_id"),
            "teacher_name": t.get("name"),
            "teacher_email": t.get("email"),
            "student_count": await db["enrollments"].count_documents({"class_id": cid}),
            "assignment_count": await db["assignments"].count_documents({"class_id": cid}),
            "quiz_count": await db["quizzes"].count_documents({"class_id": cid}),
            "created_at": c.get("created_at"),
        })
    return out
