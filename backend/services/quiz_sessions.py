"""
Quiz sessions: one server-side start time per (quiz, student).

Two /start requests can arrive together (double click, a second tab, a retried request).
Both must come back with the same started_at: the unique index on quiz_sessions turns the
second insert into a DuplicateKeyError, which is then simply the other request's session.
"""
from datetime import datetime

from pymongo.errors import DuplicateKeyError


async def get_or_create_session(sessions, quiz_id: str, student_id: str, now: datetime) -> datetime:
    """Return the start time of this student's session for the quiz, creating it at `now` if needed."""
    query = {"quiz_id": quiz_id, "student_id": student_id}
    session = await sessions.find_one(query)
    if session:
        return session["started_at"]
    try:
        await sessions.insert_one({"quiz_id": quiz_id, "student_id": student_id, "started_at": now})
        return now
    except DuplicateKeyError:
        session = await sessions.find_one(query)
        if session:
            return session["started_at"]
        raise
