"""Role dependencies: admins have every teacher privilege; student-only stays student-only."""
import sys
from pathlib import Path

import pytest
from fastapi import HTTPException

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from routers.deps import TEACHER_ROLES, get_current_admin, get_current_student, get_current_teacher, is_teacher_like  # noqa: E402


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["teacher", "admin"])
async def test_teacher_check_accepts_teacher_and_admin(role):
    user = {"role": role, "id": "x"}
    assert await get_current_teacher(user) is user


@pytest.mark.asyncio
async def test_teacher_check_rejects_student():
    with pytest.raises(HTTPException) as exc:
        await get_current_teacher({"role": "student"})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
@pytest.mark.parametrize("role", ["teacher", "admin"])
async def test_student_check_rejects_non_students(role):
    with pytest.raises(HTTPException) as exc:
        await get_current_student({"role": role})
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_admin_check_rejects_teacher():
    with pytest.raises(HTTPException) as exc:
        await get_current_admin({"role": "teacher"})
    assert exc.value.status_code == 403


def test_is_teacher_like():
    assert set(TEACHER_ROLES) == {"teacher", "admin"}
    assert is_teacher_like({"role": "admin"})
    assert not is_teacher_like({"role": "student"})
    assert not is_teacher_like(None)
