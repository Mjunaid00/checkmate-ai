"""
Create or promote an admin account directly in MongoDB (works whether or not the backend
is running). Public registration cannot create admins, and the backend only bootstraps a
default admin when none exists, so this is the way to add one.

    cd <project>
    python scripts\\create_admin.py --email admin@university.edu --name Admin

The password is read from the CHECKMATE_ADMIN_PASSWORD environment variable or prompted
for (hidden). --password also works but lands in your shell history. An existing user with
that email is promoted to admin (and gets the new password when one is given).

Uses backend/.env (MONGO_URI, DATABASE_NAME) and the backend's own password hashing, so the
account logs in exactly like one created through the API. Review before use.
"""
import argparse
import getpass
import os
import re
import sys
from datetime import datetime
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND))

import config  # noqa: E402  (loads backend/.env)
from core.security import hash_password  # noqa: E402
from pymongo import MongoClient  # noqa: E402

NAME_RE = re.compile(r"^[A-Za-z0-9_]+$")  # same rule as routers/auth.py
MIN_PASSWORD = 6  # the API's minimum (models/user.py); enforced here only as a warning


def mask_uri(uri: str) -> str:
    return re.sub(r"//([^:/@]+):([^@]+)@", r"//\1:***@", uri)


def main() -> int:
    ap = argparse.ArgumentParser(description="Create or promote a CheckMate admin account.")
    ap.add_argument("--email", required=True)
    ap.add_argument("--name", default="Admin", help="letters, digits, underscore; at least 3 letters")
    ap.add_argument("--password", default=None, help="prefer the prompt or CHECKMATE_ADMIN_PASSWORD")
    args = ap.parse_args()

    email = args.email.strip()
    name = args.name.strip()
    if "@" not in email:
        print("error: --email must be an email address")
        return 2
    if not NAME_RE.fullmatch(name) or sum(ch.isalpha() for ch in name) < 3:
        print("error: --name may only contain letters, digits and underscore, with at least 3 letters")
        return 2

    client = MongoClient(config.MONGO_URI, serverSelectionTimeoutMS=5000)
    users = client[config.DATABASE_NAME]["users"]
    try:
        client.admin.command("ping")
    except Exception as exc:
        print(f"error: MongoDB not reachable at {mask_uri(config.MONGO_URI)}: {exc}")
        return 1

    existing = users.find_one({"email": email})
    password = args.password if args.password is not None else os.environ.get("CHECKMATE_ADMIN_PASSWORD")
    if password is None:
        if not sys.stdin.isatty():
            print("error: no password given (set CHECKMATE_ADMIN_PASSWORD or run interactively)")
            return 2
        prompt = "New password (leave empty to keep the current one): " if existing else "Password for the new admin: "
        password = getpass.getpass(prompt)
        if existing and password == "":
            password = None
        elif password == "":
            print("error: empty password")
            return 2
    if password is not None and len(password) < MIN_PASSWORD:
        print(f"warning: password is shorter than the app's minimum of {MIN_PASSWORD} characters; "
              "login works, but change it to a longer one from Settings.")

    if existing:
        update = {"role": "admin", "is_active": True}
        if password is not None:
            update["hashed_password"] = hash_password(password)
        users.update_one({"_id": existing["_id"]}, {"$set": update})
        what = "promoted to admin" + (" and password updated" if password is not None else "")
    else:
        users.insert_one({
            "name": name,
            "email": email,
            "hashed_password": hash_password(password),
            "role": "admin",
            "created_at": datetime.utcnow(),
            "is_active": True,
        })
        what = "created"

    print(f"admin {email} {what} in database '{config.DATABASE_NAME}' at {mask_uri(config.MONGO_URI)}")
    others = [u["email"] for u in users.find({"role": "admin", "email": {"$ne": email}})]
    if others:
        print("other admin accounts:", ", ".join(others))
    return 0


if __name__ == "__main__":
    sys.exit(main())
