"""
Audit log of teacher / admin overrides (quiz attempt resets, allowed resubmissions).
Admins see everything; teachers see their own entries.
"""
from fastapi import APIRouter, Depends, Query

from database import get_db
from routers.deps import get_current_teacher
from services.audit import map_audit

router = APIRouter(prefix="/audit", tags=["audit"])


@router.get("/")
async def list_audit(
    limit: int = Query(100, ge=1, le=500),
    current_user: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    query = {} if current_user.get("role") == "admin" else {"actor_id": current_user["id"]}
    docs = await db["audit_log"].find(query).sort("created_at", -1).to_list(length=limit)
    return [map_audit(d) for d in docs]
