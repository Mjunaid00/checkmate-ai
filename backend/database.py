import re

from motor.motor_asyncio import AsyncIOMotorClient

from config import MONGO_URI, DATABASE_NAME

# Holders — populated on startup
client: AsyncIOMotorClient = None
db = None


def mask_uri(uri: str) -> str:
    """Hide credentials in a connection string before logging it."""
    return re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:****@", uri or "")


async def connect_db() -> None:
    """Open the Motor client and verify the connection is reachable."""
    global client, db
    client = AsyncIOMotorClient(
        MONGO_URI,
        serverSelectionTimeoutMS=5000,  # fail fast if unreachable
    )
    db = client[DATABASE_NAME]
    try:
        await client.admin.command("ping")
        print(f"[OK] MongoDB connected -> {DATABASE_NAME} ({mask_uri(MONGO_URI)})")
    except Exception as exc:
        print(f"[WARN] MongoDB not reachable: {exc}")
        print("[INFO] Server continuing - check MONGO_URI in backend/.env and that the MongoDB service is running")


async def close_db() -> None:
    """Close the Motor client gracefully."""
    global client
    if client:
        client.close()
        print("[INFO] MongoDB connection closed")


def get_db():
    """FastAPI dependency - returns the active database handle."""
    return db


async def ping() -> dict:
    """Connectivity probe used by /health/full."""
    if client is None:
        return {"ok": False, "error": "not connected", "uri": mask_uri(MONGO_URI), "database": DATABASE_NAME}
    try:
        await client.admin.command("ping")
        return {"ok": True, "uri": mask_uri(MONGO_URI), "database": DATABASE_NAME}
    except Exception as exc:
        return {"ok": False, "error": str(exc)[:200], "uri": mask_uri(MONGO_URI), "database": DATABASE_NAME}


# (collection, keys, options) — created at startup, best effort.
INDEXES = [
    ("users", [("email", 1)], {"unique": True, "name": "uniq_email"}),
    ("submissions", [("assignment_id", 1), ("student_id", 1)], {"unique": True, "name": "uniq_submission_per_student"}),
    ("submissions", [("student_id", 1), ("created_at", -1)], {"name": "student_recent"}),
    ("enrollments", [("class_id", 1), ("student_id", 1)], {"unique": True, "name": "uniq_enrollment"}),
    ("quiz_attempts", [("quiz_id", 1), ("student_id", 1)], {"unique": True, "name": "uniq_attempt"}),
    ("notifications", [("user_id", 1), ("created_at", -1)], {"name": "user_recent"}),
    ("messages", [("to_user_id", 1), ("created_at", -1)], {"name": "recipient_recent"}),
    ("assignments", [("class_id", 1), ("created_at", -1)], {"name": "class_recent"}),
]


async def ensure_indexes() -> None:
    """Create the indexes the app relies on. Never raises; logs what it could not do."""
    if db is None:
        return
    status = await ping()
    if not status["ok"]:
        print("[indexes] MongoDB unreachable, skipping index creation")
        return
    for coll, keys, opts in INDEXES:
        try:
            await db[coll].create_index(keys, **opts)
        except Exception as exc:
            # Typically: existing duplicate documents block a unique index.
            print(f"[WARN] Could not create index {opts.get('name')} on {coll}: {str(exc)[:160]}")
