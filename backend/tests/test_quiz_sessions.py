"""
Quiz sessions: two simultaneous /start calls (double click, two tabs) must share one start time
instead of the second one failing on the unique index.
"""
import asyncio
import sys
from datetime import datetime
from pathlib import Path

from pymongo.errors import DuplicateKeyError

BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


class FakeSessions:
    def __init__(self, existing=None, collide_with=None):
        self.doc = existing
        self.collide_with = collide_with
        self.inserted = []

    async def find_one(self, query):
        return self.doc

    async def insert_one(self, doc):
        if self.collide_with is not None:
            # another request inserted first: the index rejects ours and theirs is what find_one now returns
            self.doc = {**doc, "started_at": self.collide_with}
            raise DuplicateKeyError("E11000 duplicate key error")
        self.doc = doc
        self.inserted.append(doc)


def test_creates_a_session_when_none_exists():
    from services.quiz_sessions import get_or_create_session
    now = datetime(2026, 11, 9, 4, 0, 0)
    col = FakeSessions()
    started = asyncio.run(get_or_create_session(col, "quiz1", "stu1", now))
    assert started == now
    assert col.inserted == [{"quiz_id": "quiz1", "student_id": "stu1", "started_at": now}]


def test_reuses_the_existing_session_start():
    from services.quiz_sessions import get_or_create_session
    earlier = datetime(2026, 11, 9, 3, 50, 0)
    col = FakeSessions(existing={"quiz_id": "quiz1", "student_id": "stu1", "started_at": earlier})
    started = asyncio.run(get_or_create_session(col, "quiz1", "stu1", datetime(2026, 11, 9, 4, 0, 0)))
    assert started == earlier
    assert col.inserted == []


def test_a_lost_insert_race_returns_the_winners_start_time():
    from services.quiz_sessions import get_or_create_session
    winner = datetime(2026, 11, 9, 3, 59, 59, 500000)
    col = FakeSessions(collide_with=winner)
    started = asyncio.run(get_or_create_session(col, "quiz1", "stu1", datetime(2026, 11, 9, 4, 0, 0)))
    assert started == winner
