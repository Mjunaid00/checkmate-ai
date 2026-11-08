"""
Audit trail for teacher / admin overrides (quiz attempt resets, allowed resubmissions,
manual grade changes). Entries live in the `audit_log` collection.
"""
from datetime import datetime
from typing import Any, Dict, Optional

MIN_REASON_CHARS = 3


class AuditError(ValueError):
    """The override cannot be recorded (for example: no reason given)."""


def audit_entry(actor: Dict[str, Any], action: str, target_type: str, target_id: Any,
                reason: Optional[str], details: Optional[Dict[str, Any]] = None,
                require_reason: bool = True) -> Dict[str, Any]:
    """Overrides (resets, removals, edits of someone else's record) need a reason; plain
    administrative actions (account edits) are logged without one."""
    reason = (reason or "").strip()
    if require_reason and len(reason) < MIN_REASON_CHARS:
        raise AuditError(f"A reason (at least {MIN_REASON_CHARS} characters) is required")
    return {
        "actor_id": actor.get("id"),
        "actor_name": actor.get("name"),
        "actor_role": actor.get("role"),
        "action": action,
        "target_type": target_type,
        "target_id": str(target_id),
        "reason": reason,
        "details": dict(details or {}),
        "created_at": datetime.utcnow(),
    }


async def record_audit(db, actor: Dict[str, Any], action: str, target_type: str, target_id: Any,
                       reason: Optional[str], details: Optional[Dict[str, Any]] = None,
                       require_reason: bool = True) -> Dict[str, Any]:
    """Validate and store one audit entry; returns it (with `_id`)."""
    entry = audit_entry(actor, action, target_type, target_id, reason, details, require_reason=require_reason)
    result = await db["audit_log"].insert_one(entry)
    entry["_id"] = result.inserted_id
    return entry


def map_audit(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out["audit_id"] = str(doc.get("_id"))
    out.pop("_id", None)
    return out
