"""
Who may change a teacher-owned record: the owning teacher, or an admin (full control).
Admin changes to someone else's record are overrides and must be audited with a reason.
"""
import sys
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

TEACHER = {"id": "t1", "role": "teacher"}
OTHER_TEACHER = {"id": "t2", "role": "teacher"}
ADMIN = {"id": "a1", "role": "admin"}
STUDENT = {"id": "s1", "role": "student"}


def test_owner_filter_restricts_teachers_but_not_admins():
    from services.permissions import owner_filter
    assert owner_filter(TEACHER) == {"teacher_id": "t1"}
    assert owner_filter(ADMIN) == {}


def test_can_manage_owner_and_admin_only():
    from services.permissions import can_manage
    assert can_manage(TEACHER, "t1") is True
    assert can_manage(OTHER_TEACHER, "t1") is False
    assert can_manage(ADMIN, "t1") is True
    assert can_manage(STUDENT, "s1") is False


def test_is_admin_override_only_when_admin_touches_someone_elses_record():
    from services.permissions import is_admin_override
    assert is_admin_override(ADMIN, "t1") is True
    assert is_admin_override(ADMIN, "a1") is False   # admin editing their own class: ordinary edit
    assert is_admin_override(TEACHER, "t1") is False


def test_describe_changes_lists_old_and_new_values_with_iso_dates():
    from datetime import datetime
    from services.permissions import describe_changes
    before = {"title": "Old", "deadline": datetime(2026, 11, 10, 10, 0), "total_marks": 10}
    updates = {"title": "New", "deadline": None}
    assert describe_changes(before, updates) == {
        "title": {"from": "Old", "to": "New"},
        "deadline": {"from": "2026-11-10T10:00:00", "to": None},
    }
