"""
Who may change a teacher-owned record (class, assignment, quiz, submission of an assignment).

Teachers manage what they own. Admins have full control over every record; when an admin
changes a record owned by somebody else that is an override: it needs a reason and is written
to the audit log, and the owner is told.
"""
from datetime import datetime
from typing import Any, Dict, Optional


def owner_filter(user: Dict[str, Any]) -> Dict[str, Any]:
    """Extra query terms that restrict a lookup to the caller's own records (none for admins)."""
    if (user or {}).get("role") == "admin":
        return {}
    return {"teacher_id": user["id"]}


def can_manage(user: Dict[str, Any], owner_id: Optional[str]) -> bool:
    role = (user or {}).get("role")
    if role == "admin":
        return True
    if role != "teacher":
        return False
    return owner_id is not None and str(owner_id) == str(user.get("id"))


def is_admin_override(user: Dict[str, Any], owner_id: Optional[str]) -> bool:
    """True when an admin edits a record that belongs to someone else."""
    return (user or {}).get("role") == "admin" and str(owner_id) != str(user.get("id"))


def _plain(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def describe_changes(before: Dict[str, Any], updates: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """{field: {"from": old, "to": new}} for the audit log; datetimes as ISO strings."""
    return {key: {"from": _plain(before.get(key)), "to": _plain(new)} for key, new in updates.items()}
