"""
End-to-end smoke test for a RUNNING CheckMate stack (backend + MongoDB + LM Studio).

    cd <project>\backend
    python ..\scripts\e2e_smoke.py

What it does (takes 2-6 minutes, most of it model inference):
  1. registers a throw-away teacher + student (e2e_<role>_<tag>@example.com)
  2. checks the auth fixes (duplicate register -> 400, wrong password -> 401)
  3. creates a class, uploads an assignment with a UTC deadline, enrols the student
  4. generates an answer image that carries the institution header, submits it
  5. waits for the background grading pipeline, prints score + feedback summary
  6. checks teacher dashboard stats, submission access, deadline maths, quiz generation

The accounts it creates stay in the database; delete them from the Admin panel
if you do not want them. Review this script before running it against a
database you care about.
"""
import json
import sys
import tempfile
import time
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from PIL import Image, ImageDraw, ImageFont

BASE = "http://localhost:8000"
ROOT = Path(__file__).resolve().parent.parent
RUBRIC = next(iter(sorted(ROOT.glob("uploads/assignments/*/rubric.*"))), None)
PASSWORD = "e2epass123"  # throw-away test accounts only

HEADER_LINES = [
    "Shaheed Zulfikar Ali Bhutto Institute of",
    "Science and Technology University",
]
ANSWER_LINES = [
    "Q1. Explain LIFO and the stack data structure.",
    "LIFO means Last In, First Out: the most recently added item is removed first.",
    "A stack supports push (add to top), pop (remove from top) and peek (read top).",
    "Both push and pop run in O(1) time. Stacks are used for function calls,",
    "undo operations, expression evaluation and depth-first search.",
    "",
    "Q2. Give an example.",
    "Pushing 1, 2, 3 then popping returns 3, 2, 1. A stack overflow happens when",
    "push is called on a full fixed-size stack; underflow when pop is called on an",
    "empty stack.",
]

tag = uuid.uuid4().hex[:6]
c = httpx.Client(timeout=120)
t0 = time.time()


def log(msg: str) -> None:
    print(f"[{time.time() - t0:6.1f}s] {msg}", flush=True)


def auth(tok: str) -> dict:
    return {"Authorization": f"Bearer {tok}"}


def register(role: str):
    email = f"e2e_{role}_{tag}@example.com"
    r = c.post(f"{BASE}/auth/register", json={"name": f"e2e_{role}_{tag}", "email": email, "password": PASSWORD, "role": role})
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()["access_token"], email


def make_answer_image(path: Path) -> None:
    img = Image.new("RGB", (1240, 1600), "white")
    d = ImageDraw.Draw(img)
    try:
        big = ImageFont.truetype("C:/Windows/Fonts/arialbd.ttf", 40)
        body = ImageFont.truetype("C:/Windows/Fonts/arial.ttf", 34)
    except Exception:
        big = body = ImageFont.load_default()
    y = 50
    for ln in HEADER_LINES:
        d.text((60, y), ln, font=big, fill="black")
        y += 50
    d.text((60, y + 40), "Data Structures - Assignment 1    Name: E2E Student    ID: E2E-001", font=body, fill="black")
    y += 150
    for ln in ANSWER_LINES:
        d.text((60, y), ln, font=body, fill="black")
        y += 52
    img.save(path)


def main() -> int:
    if RUBRIC is None:
        print("No rubric file found under uploads/assignments/*/ — upload one assignment first.")
        return 2

    health = c.get(f"{BASE}/health/full").json()
    log(f"/health/full -> {health['status']}")
    if health["status"] != "ok":
        print(json.dumps(health["checks"], indent=2))
        return 2

    t_tok, t_email = register("teacher")
    s_tok, s_email = register("student")
    log("registered teacher + student")

    r = c.post(f"{BASE}/auth/register", json={"name": f"e2e_dup_{tag}", "email": t_email, "password": PASSWORD, "role": "teacher"})
    log(f"duplicate register -> {r.status_code} (expect 400)")
    assert r.status_code == 400
    r = c.post(f"{BASE}/auth/login", data={"username": t_email, "password": "wrong"})
    log(f"wrong password -> {r.status_code} (expect 401)")
    assert r.status_code == 401

    r = c.post(f"{BASE}/classes/", json={"name": f"E2E Class {tag}"}, headers=auth(t_tok))
    r.raise_for_status()
    class_id = r.json()["class_id"]
    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat().replace("+00:00", "Z")
    mime = "application/pdf" if RUBRIC.suffix.lower() == ".pdf" else ("image/jpeg" if RUBRIC.suffix.lower() in (".jpg", ".jpeg") else "image/png")
    with RUBRIC.open("rb") as f:
        r = c.post(f"{BASE}/assignments/", headers=auth(t_tok),
                   data={"class_id": class_id, "title": f"E2E Assignment {tag}", "total_marks": "10",
                         "grading_prompt": "Be concise.", "deadline": deadline},
                   files={"file": (RUBRIC.name, f, mime)})
    assert r.status_code == 200, (r.status_code, r.text)
    assignment_id = r.json()["assignment_id"]
    log(f"assignment created from {RUBRIC.name}; deadline stored = {r.json()['deadline']} (sent {deadline})")

    r = c.post(f"{BASE}/enrollment/{class_id}", json={"student_id_number": "E2E-001"}, headers=auth(s_tok))
    r.raise_for_status()
    r = c.get(f"{BASE}/submissions/assignment/{assignment_id}", headers=auth(s_tok))
    assert r.status_code == 200 and r.json() == [], r.text
    log("student enrolled; student sees only own submissions (none yet)")

    with tempfile.TemporaryDirectory() as tmp:
        answer = Path(tmp) / "answer.png"
        make_answer_image(answer)
        with answer.open("rb") as f:
            r = c.post(f"{BASE}/submissions/", headers=auth(s_tok), data={"assignment_id": assignment_id},
                       files={"file": ("answer.png", f, "image/png")})
    assert r.status_code == 200, r.text
    submission_id = r.json()["submission_id"]
    log(f"submission accepted (institution header verified by OCR): {submission_id}")

    final = None
    stop_at = time.time() + 15 * 60
    while time.time() < stop_at:
        r = c.get(f"{BASE}/submissions/student", headers=auth(s_tok))
        r.raise_for_status()
        sub = next(s for s in r.json() if s["submission_id"] == submission_id)
        if sub["status"] in ("graded", "failed"):
            final = sub
            break
        time.sleep(5)
    assert final, "grading did not finish within 15 minutes"
    log(f"grading finished: status={final['status']} score={final.get('score')}/{final['total_marks']}")
    print("   feedback:", (final.get("feedback") or "")[:200])
    ef = final.get("explainable_feedback") or {}
    print("   criteria:", len(ef.get("criteria") or []), "| keys:", sorted(ef.keys()))
    assert final["status"] == "graded", final.get("feedback")

    r = c.get(f"{BASE}/dashboard/stats", headers=auth(t_tok))
    r.raise_for_status()
    log(f"teacher dashboard stats -> {r.json()}")
    assert r.json()["total_exams"] == 1 and r.json()["graded_exams"] == 1

    r = c.get(f"{BASE}/dashboard/exams/{submission_id}", headers=auth(t_tok))
    assert r.status_code == 200, r.text
    r = c.get(f"{BASE}/analytics/teacher/deadlines", headers=auth(t_tok))
    item = next(i for i in r.json()["items"] if i["id"] == assignment_id)
    log(f"deadline item -> status={item['status']} remaining={item['time_remaining_seconds']}s")
    assert item["status"] == "open" and 80000 < item["time_remaining_seconds"] <= 86400

    r = c.post(f"{BASE}/quizzes/generate", json={"topic": "Photosynthesis basics", "num_questions": 3}, headers=auth(t_tok))
    log(f"quiz generate -> {r.status_code} count={r.json().get('count') if r.status_code == 200 else r.text[:200]}")
    assert r.status_code == 200 and r.json()["count"] >= 1

    log("ALL E2E CHECKS PASSED")
    print(json.dumps({"class_id": class_id, "assignment_id": assignment_id, "submission_id": submission_id,
                      "teacher": t_email, "student": s_email}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
