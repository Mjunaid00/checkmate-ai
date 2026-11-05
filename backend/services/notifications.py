"""
Notifications Service
- Persist user-targeted notifications in MongoDB
- Categories: enrollment, submission, grading, message, quiz, assignment
"""
from datetime import datetime
from typing import Optional


async def notify_user(
    db,
    user_id: str,
    title: str,
    body: str,
    link: Optional[str] = None,
    category: str = "general",
) -> None:
    """Insert a notification for a user."""
    if not user_id:
        return
    try:
        await db["notifications"].insert_one({
            "user_id": user_id,
            "title": title,
            "body": body,
            "link": link,
            "category": category,
            "read": False,
            "created_at": datetime.utcnow(),
        })
    except Exception as e:
        # Notifications are best-effort; never break the main flow
        print(f"[notifications] Failed to insert: {e}")
