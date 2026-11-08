"""
Live end-to-end checks of the admin's full control: class browser, deadline changes on another
teacher's assignment and quiz (reason required, audited, teacher notified), viewing and removing a
student's submission on request, and account management (email, password, deactivate, delete).

    Stop the stack, then start the backend on a throwaway database with the header check off:
      set DATABASE_NAME=checkmate_ai_e2e
      set REQUIRE_INSTITUTION_HEADER=false
    python scripts\\e2e_admin.py --db checkmate_ai_e2e [--drop]

Logs in as the bootstrap admin (admin@checkmate.ai / admin123, created on a fresh database) or
creates a throwaway admin directly in the database. Registers throwaway e2e_* accounts.
"""
import argparse
import io
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from pymongo import MongoClient

BASE = "http://localhost:8000"
PASSWORD = "e2epass123"  # throw-away test accounts only
TAG = uuid.uuid4().hex[:6]
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' - ' + str(detail)[:160]) if detail else ''}")
    return ok


def login(c, email, password):
    r = c.post(f"{BASE}/auth/login", data={"username": email, "password": password})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"} if r.status_code == 200 else None
    return r, headers


def register(c, role):
    email = f"e2e_{role}_{TAG}@example.com"
    r = c.post(f"{BASE}/auth/register", json={"name": f"e2e_{role}_{TAG}", "email": email, "password": PASSWORD, "role": role})
    assert r.status_code in (200, 201), r.text
    r, headers = login(c, email, PASSWORD)
    assert headers, r.text
    me = c.get(f"{BASE}/auth/me", headers=headers).json()
    return email, headers, me


def admin_headers(c, db):
    r, headers = login(c, "admin@checkmate.ai", "admin123")
    if headers:
        return headers
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
    from core.security import hash_password  # noqa: E402
    email = f"e2e_admin_{TAG}@example.com"
    db["users"].insert_one({"name": f"e2e_admin_{TAG}", "email": email, "hashed_password": hash_password(PASSWORD),
                            "role": "admin", "created_at": datetime.utcnow(), "is_active": True})
    r, headers = login(c, email, PASSWORD)
    assert headers, r.text
    return headers


def iso_in(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="checkmate_ai_e2e")
    ap.add_argument("--drop", action="store_true")
    args = ap.parse_args()

    c = httpx.Client(timeout=300)
    db = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)[args.db]
    admin = admin_headers(c, db)
    t_email, teacher, t_me = register(c, "teacher")
    s_email, student, s_me = register(c, "student")
    print(f"registered teacher/student (tag {TAG}) in database {args.db}")

    cls = c.post(f"{BASE}/classes/", json={"name": f"E2E Admin Class {TAG}"}, headers=teacher).json()
    class_id = cls["class_id"]
    c.post(f"{BASE}/enrollment/{class_id}", json={"student_id_number": f"E2E-{TAG}"}, headers=student)

    from PIL import Image
    png = io.BytesIO()
    Image.new("RGB", (200, 200), "white").save(png, format="PNG")
    r = c.post(f"{BASE}/assignments/", data={"class_id": class_id, "title": f"A {TAG}", "total_marks": "10", "deadline": iso_in(1)},
               files={"file": ("rubric.png", png.getvalue(), "image/png")}, headers=teacher)
    assert r.status_code == 200, r.text
    assignment_id = r.json()["assignment_id"]
    r = c.post(f"{BASE}/quizzes/", json={"class_id": class_id, "title": f"Q {TAG}", "time_limit_minutes": 5, "deadline": iso_in(1),
                                         "questions": [{"type": "mcq", "question_text": "2+2?", "options": ["3", "4", "5", "6"], "correct_index": 1}]},
               headers=teacher)
    assert r.status_code == 200, r.text
    quiz_id = r.json()["quiz_id"]

    # student submits (header check disabled on this backend)
    r = c.post(f"{BASE}/submissions/", data={"assignment_id": assignment_id},
               files={"file": ("answer.png", png.getvalue(), "image/png")}, headers=student)
    check("student submission accepted (needs REQUIRE_INSTITUTION_HEADER=false)", r.status_code == 200, (r.status_code, r.text[:120]))
    submission_id = r.json().get("submission_id") if r.status_code == 200 else None

    # ── class browser ────────────────────────────────────────────────────────
    r = c.get(f"{BASE}/admin/classes", headers=admin)
    row = next((x for x in r.json() if x["class_id"] == class_id), None) if r.status_code == 200 else None
    check("admin lists every class with its teacher", row is not None and row["teacher_email"] == t_email, (r.status_code, row))
    check("class row carries counts", bool(row) and row["student_count"] == 1 and row["assignment_count"] == 1 and row["quiz_count"] == 1, row)
    r = c.get(f"{BASE}/admin/classes", headers=teacher)
    check("teachers cannot use the admin class browser (403)", r.status_code == 403, r.status_code)
    r = c.get(f"{BASE}/assignments/class/{class_id}", headers=admin)
    check("admin sees the class assignments", r.status_code == 200 and len(r.json()) == 1, r.status_code)
    r = c.get(f"{BASE}/quizzes/class/{class_id}", headers=admin)
    check("admin sees the class quizzes", r.status_code == 200 and len(r.json()) == 1, r.status_code)

    # ── assignment deadline ──────────────────────────────────────────────────
    audit_before = len(c.get(f"{BASE}/audit/", headers=admin).json())
    r = c.patch(f"{BASE}/assignments/{assignment_id}", params={"deadline": iso_in(3)}, headers=admin)
    check("admin deadline change without a reason is refused (400)", r.status_code == 400, (r.status_code, r.text[:100]))
    r = c.patch(f"{BASE}/assignments/{assignment_id}", params={"deadline": iso_in(3), "reason": "Student request: exam week"}, headers=admin)
    ok = r.status_code == 200 and r.json()["deadline"][:10] == iso_in(3)[:10]
    check("admin changes another teacher's assignment deadline", ok, (r.status_code, r.text[:120]))
    entries = c.get(f"{BASE}/audit/", headers=admin).json()
    e = next((x for x in entries if x["action"] == "assignment_updated" and x["target_id"] == assignment_id), None)
    check("deadline change is audited with old/new values", e is not None and e["actor_role"] == "admin" and "deadline" in e["details"].get("changes", {}), e and e["details"])
    notes = c.get(f"{BASE}/notifications/", headers=teacher).json()
    check("owning teacher is notified of the admin change", any("administrator" in (n.get("body") or "").lower() for n in notes), [n.get("title") for n in notes][:3])
    r = c.patch(f"{BASE}/assignments/{assignment_id}", params={"deadline": iso_in(4)}, headers=teacher)
    check("teacher still edits their own deadline without a reason", r.status_code == 200, (r.status_code, r.text[:100]))
    check("teacher's own edit is not audited", len(c.get(f"{BASE}/audit/", headers=admin).json()) == audit_before + 1)

    # ── quiz deadline ────────────────────────────────────────────────────────
    r = c.patch(f"{BASE}/quizzes/{quiz_id}", json={"deadline": iso_in(3)}, headers=admin)
    check("admin quiz deadline change without a reason is refused (400)", r.status_code == 400, r.status_code)
    r = c.patch(f"{BASE}/quizzes/{quiz_id}", json={"deadline": iso_in(3), "reason": "Requested by the class rep"}, headers=admin)
    check("admin changes another teacher's quiz deadline", r.status_code == 200 and r.json()["deadline"][:10] == iso_in(3)[:10], (r.status_code, r.text[:120]))
    entries = c.get(f"{BASE}/audit/", headers=admin).json()
    check("quiz deadline change is audited", any(x["action"] == "quiz_updated" and x["target_id"] == quiz_id for x in entries))

    # ── submissions: view and remove on request ──────────────────────────────
    r = c.get(f"{BASE}/submissions/assignment/{assignment_id}", headers=admin)
    check("admin sees the student's submission", r.status_code == 200 and len(r.json()) == 1, (r.status_code, r.text[:100]))
    if submission_id:
        r = c.post(f"{BASE}/submissions/{submission_id}/allow-resubmission", json={"reason": ""}, headers=admin)
        check("removal without a reason is refused (400)", r.status_code == 400, r.status_code)
        r = c.post(f"{BASE}/submissions/{submission_id}/allow-resubmission", json={"reason": "Student uploaded the wrong file"}, headers=admin)
        check("admin removes the submission", r.status_code == 200, (r.status_code, r.text[:100]))
        check("submission is gone", len(c.get(f"{BASE}/submissions/assignment/{assignment_id}", headers=admin).json()) == 0)
        entries = c.get(f"{BASE}/audit/", headers=admin).json()
        check("removal is audited under the admin", any(x["action"] == "submission_reset" and x["target_id"] == submission_id and x["actor_role"] == "admin" for x in entries))
        notes = c.get(f"{BASE}/notifications/", headers=student).json()
        check("student is told an administrator removed it", any("administrator" in (n.get("body") or "").lower() for n in notes), [(n.get("body") or "")[:60] for n in notes][:3])
        r = c.post(f"{BASE}/submissions/", data={"assignment_id": assignment_id},
                   files={"file": ("answer2.png", png.getvalue(), "image/png")}, headers=student)
        check("student can submit again", r.status_code == 200, (r.status_code, r.text[:100]))

    # ── accounts ─────────────────────────────────────────────────────────────
    sid = s_me["id"]
    new_email = f"e2e_student_{TAG}_renamed@example.com"
    r = c.patch(f"{BASE}/admin/users/{sid}", json={"email": new_email}, headers=admin)
    check("admin changes a student's email", r.status_code == 200 and r.json()["email"] == new_email, (r.status_code, r.text[:100]))
    r = c.patch(f"{BASE}/admin/users/{sid}", json={"email": t_email}, headers=admin)
    check("email already used by another account is refused (409)", r.status_code == 409, r.status_code)
    r, h = login(c, new_email, PASSWORD)
    check("student logs in with the new email", h is not None, r.status_code)
    r = c.post(f"{BASE}/admin/users/{sid}/password", json={"new_password": "newpass999"}, headers=admin)
    r2, h = login(c, new_email, "newpass999")
    check("admin password reset works", r.status_code == 200 and h is not None, (r.status_code, r2.status_code))
    r = c.patch(f"{BASE}/admin/users/{sid}", json={"is_active": False}, headers=admin)
    r2, h = login(c, new_email, "newpass999")
    check("deactivated student cannot log in", r.status_code == 200 and h is None and r2.status_code in (401, 403), r2.status_code)
    r = c.patch(f"{BASE}/admin/users/{sid}", json={"is_active": True, "role": "teacher"}, headers=admin)
    check("admin changes the role", r.status_code == 200 and r.json()["role"] == "teacher", r.text[:100])
    entries = c.get(f"{BASE}/audit/", headers=admin).json()
    kinds = {x["action"] for x in entries if x["target_id"] == sid}
    check("account changes are audited (update + password reset)", {"user_updated", "password_reset"} <= kinds, kinds)
    r = c.delete(f"{BASE}/admin/users/{sid}", headers=admin)
    check("admin deletes the account", r.status_code == 204, r.status_code)
    entries = c.get(f"{BASE}/audit/", headers=admin).json()
    check("deletion is audited", any(x["action"] == "user_deleted" and x["target_id"] == sid for x in entries))

    passed = sum(1 for _, ok, _ in RESULTS if ok)
    print(f"\n{passed}/{len(RESULTS)} checks passed")
    if args.drop:
        MongoClient("mongodb://localhost:27017").drop_database(args.db)
        print(f"dropped database {args.db}")
    return 0 if passed == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
