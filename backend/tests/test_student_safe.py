"""
What students are allowed to see: no grading prompt, no rubric keywords before the deadline,
and a deactivated account cannot keep using an old token.
"""
import sys
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from fastapi import HTTPException

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


def test_student_safe_assignment_drops_grading_prompt_only():
    from services.student_safe import student_safe_assignment
    doc = {"assignment_id": "a1", "title": "T", "grading_prompt": "award marks for mentioning osmosis", "total_marks": 10}
    out = student_safe_assignment(doc)
    assert out["grading_prompt"] is None
    assert out["title"] == "T" and out["total_marks"] == 10
    assert doc["grading_prompt"] is not None, "must not mutate the stored document"


def test_keyword_lists_hidden_before_deadline():
    from services.student_safe import redact_keyword_analysis
    now = datetime(2026, 11, 5, 12, 0)
    sub = {"explainable_feedback": {"xai": {"keyword_analysis": {
        "rubric_keywords": ["osmosis", "diffusion"], "matched_keywords": ["osmosis"],
        "missing_keywords": ["diffusion"], "keyword_coverage": 50.0}}}}
    out = redact_keyword_analysis(sub, deadline=now + timedelta(days=1), now=now)
    ka = out["explainable_feedback"]["xai"]["keyword_analysis"]
    assert ka["rubric_keywords"] == [] and ka["matched_keywords"] == [] and ka["missing_keywords"] == []
    assert ka["keyword_coverage"] == 50.0
    assert ka["hidden_until_deadline"] is True
    assert sub["explainable_feedback"]["xai"]["keyword_analysis"]["missing_keywords"] == ["diffusion"], "no mutation"


def test_keyword_lists_hidden_when_no_deadline():
    from services.student_safe import redact_keyword_analysis
    now = datetime(2026, 11, 5, 12, 0)
    sub = {"explainable_feedback": {"xai": {"keyword_analysis": {"rubric_keywords": ["a"], "matched_keywords": [], "missing_keywords": ["a"]}}}}
    assert redact_keyword_analysis(sub, deadline=None, now=now)["explainable_feedback"]["xai"]["keyword_analysis"]["hidden_until_deadline"] is True


def test_keyword_lists_visible_after_deadline():
    from services.student_safe import redact_keyword_analysis
    now = datetime(2026, 11, 5, 12, 0)
    sub = {"explainable_feedback": {"xai": {"keyword_analysis": {"rubric_keywords": ["a"], "matched_keywords": [], "missing_keywords": ["a"]}}}}
    out = redact_keyword_analysis(sub, deadline=now - timedelta(minutes=1), now=now)
    assert out["explainable_feedback"]["xai"]["keyword_analysis"]["missing_keywords"] == ["a"]
    assert not out["explainable_feedback"]["xai"]["keyword_analysis"].get("hidden_until_deadline")


def test_redaction_tolerates_submissions_without_feedback():
    from services.student_safe import redact_keyword_analysis
    assert redact_keyword_analysis({"status": "uploaded"}, deadline=None, now=datetime.utcnow()) == {"status": "uploaded"}


class _Coll:
    def __init__(self, doc):
        self.doc = doc

    async def find_one(self, *_a, **_k):
        return self.doc


class _DB:
    def __init__(self, doc):
        self.doc = doc

    def __getitem__(self, _name):
        return _Coll(self.doc)


@pytest.mark.asyncio
async def test_deactivated_user_token_is_rejected(monkeypatch):
    import routers.deps as deps
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "x@y.z"})
    db = _DB({"_id": "u1", "email": "x@y.z", "role": "student", "is_active": False})
    with pytest.raises(HTTPException) as exc:
        await deps.get_current_user(token="t", db=db)
    assert exc.value.status_code == 403
    assert "deactivated" in exc.value.detail.lower()


@pytest.mark.asyncio
async def test_active_user_passes(monkeypatch):
    import routers.deps as deps
    monkeypatch.setattr(deps, "decode_token", lambda _t: {"sub": "x@y.z"})
    db = _DB({"_id": "u1", "email": "x@y.z", "role": "student", "is_active": True})
    user = await deps.get_current_user(token="t", db=db)
    assert user["id"] == "u1"
