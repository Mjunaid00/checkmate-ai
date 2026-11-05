"""
Notifications Router — list, mark-as-read, mark-all-read, unread count.
"""
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from routers.deps import get_current_user

router = APIRouter(prefix="/notifications", tags=["notifications"])


def _map(doc: dict) -> dict:
    doc["notification_id"] = str(doc["_id"])
    doc.pop("_id", None)
    if "created_at" in doc and doc["created_at"]:
        doc["created_at"] = doc["created_at"].isoformat()
    return doc


@router.get("/")
async def list_my_notifications(
    limit: int = 50,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List the current user's notifications, newest first."""
    cursor = db["notifications"].find({"user_id": current_user["id"]}).sort("created_at", -1)
    results = await cursor.to_list(length=max(1, min(limit, 200)))
    return [_map(n) for n in results]


@router.get("/unread-count")
async def unread_count(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Return how many unread notifications the user has."""
    count = await db["notifications"].count_documents({
        "user_id": current_user["id"],
        "read": False,
    })
    return {"unread": count}


@router.patch("/{notification_id}/read")
async def mark_read(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mark a single notification as read."""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification_id")
    result = await db["notifications"].update_one(
        {"_id": ObjectId(notification_id), "user_id": current_user["id"]},
        {"$set": {"read": True}},
    )
    if result.matched_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
    return {"detail": "marked as read"}


@router.post("/read-all")
async def mark_all_read(
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Mark all of the user's notifications as read."""
    result = await db["notifications"].update_many(
        {"user_id": current_user["id"], "read": False},
        {"$set": {"read": True}},
    )
    return {"updated": result.modified_count}


@router.delete("/{notification_id}", status_code=204)
async def delete_notification(
    notification_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Delete a notification."""
    if not ObjectId.is_valid(notification_id):
        raise HTTPException(status_code=400, detail="Invalid notification_id")
    result = await db["notifications"].delete_one({
        "_id": ObjectId(notification_id),
        "user_id": current_user["id"],
    })
    if result.deleted_count == 0:
        raise HTTPException(status_code=404, detail="Notification not found")
