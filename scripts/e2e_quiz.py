"""
End-to-end check of the quiz features against a RUNNING stack (backend + MongoDB + LM Studio):

    cd <project>
    python scripts\\e2e_quiz.py --db checkmate_ai_e2e [--drop] [--skip-ai]

Covers: MCQ + true/false quizzes, server-timed single attempt (start twice -> same clock,
submit twice -> 409, expired window -> 403), answer-key lock after attempts, analytics
(distribution, weak questions, student deadlines route, ownership checks), grading prompt
hidden from students, and AI generation from a topic, a TXT and a DOCX file.

--db must be the database the backend is using (DATABASE_NAME); the script edits one quiz
session in it to simulate an expired timer and, with --drop, drops the whole database at the
end. Only ever point it at a throw-away database. Review before running elsewhere.
"""
import argparse
import io
import sys
import uuid
from datetime import datetime, timedelta, timezone

import httpx
from bson import ObjectId
from pymongo import MongoClient

BASE = "http://localhost:8000"
PASSWORD = "e2epass123"  # throw-away test accounts only
TAG = uuid.uuid4().hex[:6]
RESULTS = []


def check(name, ok, detail=""):
    RESULTS.append((name, bool(ok), detail))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}{(' - ' + str(detail)[:160]) if detail else ''}")
    return ok


def register(c, role, suffix=""):
    email = f"e2e_{role}{suffix}_{TAG}@example.com"
    r = c.post(f"{BASE}/auth/register", json={"name": f"e2e_{role}{suffix}_{TAG}", "email": email, "password": PASSWORD, "role": role})
    r.raise_for_status()
    r = c.post(f"{BASE}/auth/login", data={"username": email, "password": PASSWORD})
    r.raise_for_status()
    tok = r.json()["access_token"]
    me = c.get(f"{BASE}/auth/me", headers={"Authorization": f"Bearer {tok}"}).json()
    return {"Authorization": f"Bearer {tok}"}, me


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", required=True, help="database the backend uses (throw-away!)")
    ap.add_argument("--drop", action="store_true", help="drop the database at the end")
    ap.add_argument("--skip-ai", action="store_true", help="skip the model-backed generation checks")
    args = ap.parse_args()

    c = httpx.Client(timeout=300)
    mongo = MongoClient("mongodb://localhost:27017", serverSelectionTimeoutMS=5000)
    db = mongo[args.db]

    teacher, t_me = register(c, "teacher")
    other_teacher, _ = register(c, "teacher", suffix="2")
    student, s_me = register(c, "student")
    print(f"registered teacher/student (tag {TAG}) in database {args.db}")

    # ── class + enrolment ────────────────────────────────────────────────────
    cls = c.post(f"{BASE}/classes/", json={"name": f"E2E Quiz Class {TAG}"}, headers=teacher).json()
    class_id = cls["class_id"]
    r = c.post(f"{BASE}/enrollment/{class_id}", json={"student_id_number": f"E2E-{TAG}"}, headers=student)
    check("student enrolled", r.status_code in (200, 201), r.text[:100])

    # ── validation: true/false must have exactly two options ─────────────────
    bad = {"class_id": class_id, "title": "bad", "time_limit_minutes": 5, "questions": [
        {"type": "true_false", "question_text": "x", "options": ["True", "False", "Maybe"], "correct_index": 0}]}
    r = c.post(f"{BASE}/quizzes/", json=bad, headers=teacher)
    check("true/false with 3 options rejected (400)", r.status_code == 400, r.json().get("detail"))

    # ── create a mixed quiz ──────────────────────────────────────────────────
    deadline = (datetime.now(timezone.utc) + timedelta(days=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    quiz_body = {
        "class_id": class_id, "title": f"Mixed quiz {TAG}", "time_limit_minutes": 5, "deadline": deadline,
        "shuffle_questions": True, "shuffle_options": True, "show_correct_after": True,
        "questions": [
            {"type": "mcq", "question_text": "2 + 2 = ?", "options": ["3", "4", "5", "6"], "correct_index": 1, "marks": 2},
            {"type": "true_false", "question_text": "The Earth orbits the Sun.", "options": ["True", "False"], "correct_index": 0, "marks": 1},
            {"type": "true_false", "question_text": "Water boils at 50 C at sea level.", "options": ["True", "False"], "correct_index": 1, "marks": 1},
        ],
    }
    r = c.post(f"{BASE}/quizzes/", json=quiz_body, headers=teacher)
    check("mixed quiz created", r.status_code == 200, r.text[:120])
    quiz = r.json()
    quiz_id = quiz["quiz_id"]
    check("total marks = 4", quiz["total_marks"] == 4, quiz["total_marks"])
    check("questions keep their type", [q["type"] for q in quiz["questions"]] == ["mcq", "true_false", "true_false"])

    # ── student view hides answers, shows types ──────────────────────────────
    r = c.get(f"{BASE}/quizzes/{quiz_id}", headers=student).json()
    check("student view has no correct_index", all("correct_index" not in q for q in r["questions"]))
    check("student view carries question type", r["questions"][1]["type"] == "true_false")

    # ── start twice: same server clock, same order ───────────────────────────
    s1 = c.post(f"{BASE}/quizzes/{quiz_id}/start", headers=student)
    check("start -> 200", s1.status_code == 200, s1.text[:120])
    s1 = s1.json()
    check("start returns ends_at + seconds_left", "ends_at" in s1 and 0 < s1["seconds_left"] <= 300, s1.get("seconds_left"))
    tf = [q for q in s1["questions"] if q["type"] == "true_false"]
    check("true/false options stay True, False in order", all(q["options"] == ["True", "False"] and q["_option_map"] == [0, 1] for q in tf))
    s2 = c.post(f"{BASE}/quizzes/{quiz_id}/start", headers=student).json()
    check("second start keeps the same started_at", s2["started_at"] == s1["started_at"], (s1["started_at"], s2["started_at"]))
    check("second start keeps the same question order", [q["question_text"] for q in s2["questions"]] == [q["question_text"] for q in s1["questions"]])

    # ── submit: one MCQ wrong on purpose, true/false right ───────────────────
    answers = [-1] * 3
    for q in s1["questions"]:
        if q["type"] == "mcq":
            answers[q["_orig_idx"]] = q["_option_map"][0] if q["_option_map"][0] != 1 else q["_option_map"][1]  # a wrong option
        else:
            answers[q["_orig_idx"]] = 0 if "Earth" in q["question_text"] else 1
    r = c.post(f"{BASE}/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=student)
    check("submit -> 200", r.status_code == 200, r.text[:120])
    att = r.json()
    check("score 2/4 (true/false right, MCQ wrong)", att["score"] == 2 and att["correct_count"] == 2, (att["score"], att["correct_count"]))
    check("attempt status submitted, not late", att.get("status") == "submitted" and att.get("late_by_seconds") == 0)

    r = c.post(f"{BASE}/quizzes/{quiz_id}/submit", json={"answers": answers}, headers=student)
    check("second submit -> 409", r.status_code == 409, r.json().get("detail"))
    r = c.post(f"{BASE}/quizzes/{quiz_id}/start", headers=student)
    check("start after submit -> 409", r.status_code == 409, r.json().get("detail"))

    # ── answer key locked after attempts ─────────────────────────────────────
    r = c.patch(f"{BASE}/quizzes/{quiz_id}", json={"questions": quiz_body["questions"]}, headers=teacher)
    check("editing questions after an attempt -> 409", r.status_code == 409, r.json().get("detail"))
    r = c.patch(f"{BASE}/quizzes/{quiz_id}", json={"title": f"Mixed quiz {TAG} (renamed)"}, headers=teacher)
    check("renaming still allowed", r.status_code == 200, r.text[:80])

    # ── expired window: tamper with the session clock in the database ────────
    r = c.post(f"{BASE}/quizzes/", json={**quiz_body, "title": f"Timed quiz {TAG}", "time_limit_minutes": 1}, headers=teacher)
    quiz2 = r.json()["quiz_id"]
    st = c.post(f"{BASE}/quizzes/{quiz2}/start", headers=student)
    check("timed quiz start -> 200", st.status_code == 200)
    res = db["quiz_sessions"].update_one({"quiz_id": quiz2, "student_id": s_me["id"]},
                                         {"$set": {"started_at": datetime.utcnow() - timedelta(minutes=10)}})
    check("session clock moved 10 min back (db)", res.modified_count == 1)
    r = c.post(f"{BASE}/quizzes/{quiz2}/submit", json={"answers": [1, 0, 1]}, headers=student)
    check("submit after time limit + grace -> 403", r.status_code == 403, r.json().get("detail"))
    r = c.post(f"{BASE}/quizzes/{quiz2}/start", headers=student)
    check("start after time ran out -> 403", r.status_code == 403, r.json().get("detail"))
    check("no attempt recorded for the expired quiz", db["quiz_attempts"].count_documents({"quiz_id": quiz2}) == 0)

    # ── analytics ────────────────────────────────────────────────────────────
    r = c.get(f"{BASE}/analytics/student/deadlines", headers=student)
    check("student deadlines route reachable (was shadowed)", r.status_code == 200, r.text[:100])
    items = r.json().get("items", [])
    check("deadlines list shows the submitted quiz as completed",
          any(i.get("title", "").startswith("Mixed quiz") and i.get("status") == "completed" for i in items),
          [(i.get("title"), i.get("status")) for i in items][:4])
    ov = c.get(f"{BASE}/analytics/teacher/overview", headers=teacher).json()
    dist = ov.get("score_distribution", {}).get("quizzes", [])
    check("overview has score_distribution for quizzes", sum(b["count"] for b in dist) == 1, dist)
    weak = ov.get("weak_questions", [])
    check("weak_questions lists the missed MCQ first", weak and weak[0]["correct_rate"] == 0.0 and "2 + 2" in weak[0]["question_text"], weak[:1])
    ca = next((x for x in ov["class_averages"] if x["class_id"] == class_id), {})
    check("per-class quiz average = 50%", ca.get("quiz_average") == 50.0, ca)
    st = c.get(f"{BASE}/quizzes/{quiz_id}/stats", headers=teacher).json()
    check("quiz stats per-question correct rates", [q["correct_rate"] for q in st["question_stats"]] == [0.0, 100.0, 100.0], st["question_stats"])

    r = c.get(f"{BASE}/analytics/class/{class_id}", headers=other_teacher)
    check("other teacher cannot read class analytics (404)", r.status_code == 404, r.status_code)
    r = c.get(f"{BASE}/analytics/student/{s_me['id']}", headers=other_teacher)
    check("other teacher cannot read student analytics (404)", r.status_code == 404, r.status_code)
    r = c.get(f"{BASE}/analytics/student/{s_me['id']}", headers=teacher)
    check("own teacher can read student analytics (200)", r.status_code == 200, r.status_code)

    # ── grading prompt hidden from students ──────────────────────────────────
    png = io.BytesIO()
    from PIL import Image
    Image.new("RGB", (200, 200), "white").save(png, format="PNG")
    r = c.post(f"{BASE}/assignments/", data={"class_id": class_id, "title": f"A {TAG}", "total_marks": "10",
                                            "grading_prompt": "award marks for mentioning osmosis"},
               files={"file": ("rubric.png", png.getvalue(), "image/png")}, headers=teacher)
    check("assignment created", r.status_code == 200, r.text[:100])
    t_list = c.get(f"{BASE}/assignments/class/{class_id}", headers=teacher).json()
    s_list = c.get(f"{BASE}/assignments/class/{class_id}", headers=student).json()
    check("teacher sees grading_prompt", t_list and t_list[0]["grading_prompt"])
    check("student does NOT see grading_prompt", s_list and s_list[0]["grading_prompt"] is None, s_list[0].get("grading_prompt") if s_list else None)

    # ── short-answer quiz ────────────────────────────────────────────────────
    r = c.post(f"{BASE}/quizzes/", json={
        "class_id": class_id, "title": f"Short answers {TAG}", "time_limit_minutes": 5, "shuffle_options": False,
        "questions": [
            {"type": "short_answer", "question_text": "Capital of France?", "accepted_answers": ["Paris", "Paris, France"], "marks": 2},
            {"type": "mcq", "question_text": "1 + 1 = ?", "options": ["1", "2"], "correct_index": 1, "marks": 1},
        ]}, headers=teacher)
    check("short-answer quiz created", r.status_code == 200, r.text[:120])
    quiz3 = r.json()["quiz_id"]
    r = c.post(f"{BASE}/quizzes/", json={"class_id": class_id, "title": "bad sa", "time_limit_minutes": 5,
                                         "questions": [{"type": "short_answer", "question_text": "x", "accepted_answers": []}]}, headers=teacher)
    check("short answer without accepted answers rejected (400)", r.status_code == 400, r.json().get("detail"))
    st3 = c.post(f"{BASE}/quizzes/{quiz3}/start", headers=student).json()
    sa = next(q for q in st3["questions"] if q["type"] == "short_answer")
    check("student start hides accepted answers", "accepted_answers" not in sa and sa["options"] == [])
    ans3 = [None, None]
    for q in st3["questions"]:
        ans3[q["_orig_idx"]] = "  paris!  " if q["type"] == "short_answer" else q["_option_map"].index(1)
    r = c.post(f"{BASE}/quizzes/{quiz3}/submit", json={"answers": ans3}, headers=student)
    check("short answer graded case/punctuation-insensitively (3/3)", r.status_code == 200 and r.json()["score"] == 3, r.text[:120])
    mine = c.get(f"{BASE}/quizzes/{quiz3}/my-attempt", headers=student).json()
    sa_review = next(q for q in mine["questions"] if q["type"] == "short_answer")
    check("review shows the student's text and the accepted answers", sa_review["student_answer"] == "paris!" and sa_review["accepted_answers"] == ["Paris", "Paris, France"], sa_review)

    # ── teacher override: reset attempt (audited) ────────────────────────────
    r = c.post(f"{BASE}/quizzes/{quiz3}/attempts/{s_me['id']}/reset", json={"reason": ""}, headers=teacher)
    check("reset without a reason rejected (400)", r.status_code == 400, r.json().get("detail"))
    r = c.post(f"{BASE}/quizzes/{quiz3}/attempts/{s_me['id']}/reset", json={"reason": "browser crashed mid-quiz"}, headers=teacher)
    check("reset attempt -> 200", r.status_code == 200, r.text[:100])
    r = c.post(f"{BASE}/quizzes/{quiz3}/start", headers=student)
    check("student can start again after the reset", r.status_code == 200, r.text[:100])
    r = c.post(f"{BASE}/quizzes/{quiz3}/attempts/{s_me['id']}/reset", json={"reason": "x"}, headers=other_teacher)
    check("other teacher cannot reset (404)", r.status_code == 404, r.status_code)

    # ── teacher override: allow resubmission (audited) ───────────────────────
    a_doc = db["assignments"].find_one({"class_id": class_id})
    fake_sub = db["submissions"].insert_one({"assignment_id": str(a_doc["_id"]), "student_id": s_me["id"], "status": "uploaded",
                                            "created_at": datetime.utcnow(), "answer_file_path": "uploads/submissions/none/x.png"})
    sub_id = str(fake_sub.inserted_id)
    r = c.post(f"{BASE}/submissions/{sub_id}/allow-resubmission", json={"reason": "uploaded the wrong file"}, headers=teacher)
    check("allow resubmission -> 200", r.status_code == 200, r.text[:100])
    check("submission record removed", db["submissions"].count_documents({"_id": fake_sub.inserted_id}) == 0)
    audit = c.get(f"{BASE}/audit/", headers=teacher).json()
    actions = [e["action"] for e in audit]
    check("teacher audit log lists both overrides", actions.count("quiz_attempt_reset") == 1 and actions.count("submission_reset") == 1, actions)
    check("audit entries carry the reasons", {e["reason"] for e in audit} >= {"browser crashed mid-quiz", "uploaded the wrong file"})
    other_audit = c.get(f"{BASE}/audit/", headers=other_teacher).json()
    check("other teacher sees no entries of this teacher", other_audit == [], other_audit)

    # ── Excel / CSV reports include quizzes ──────────────────────────────────
    r = c.get(f"{BASE}/reports/class/{class_id}/xlsx", headers=teacher)
    check("class report as xlsx", r.status_code == 200 and r.content[:2] == b"PK" and "spreadsheetml" in r.headers.get("content-type", ""), (r.status_code, r.headers.get("content-type")))
    r = c.get(f"{BASE}/reports/class/{class_id}/csv", headers=teacher)
    check("class CSV has Type column with Quiz rows", r.status_code == 200 and "Type" in r.text.splitlines()[0] and ",Quiz," in r.text, r.text[:160])
    r = c.get(f"{BASE}/reports/student/{s_me['id']}/class/{class_id}/xlsx", headers=teacher)
    check("student report as xlsx", r.status_code == 200 and r.content[:2] == b"PK")

    # ── AI generation ────────────────────────────────────────────────────────
    if not args.skip_ai:
        r = c.post(f"{BASE}/quizzes/generate", json={"topic": "the water cycle", "num_questions": 3, "difficulty": "easy",
                                                     "question_type": "true_false", "grade_level": "Grade 6", "subject": "Science"}, headers=teacher)
        ok = r.status_code == 200 and r.json()["count"] >= 1 and all(q["type"] == "true_false" and q["options"] == ["True", "False"] for q in r.json()["questions"])
        check("generate true/false from topic", ok, (r.status_code, r.text[:160]))

        txt = ("Photosynthesis is the process by which green plants use sunlight to synthesise food from carbon dioxide and water. "
               "It takes place in the chloroplasts, where chlorophyll absorbs light. The light reactions produce ATP and NADPH, "
               "and the Calvin cycle uses them to fix carbon dioxide into glucose. Oxygen is released as a by-product.")
        r = c.post(f"{BASE}/quizzes/generate-from-document", data={"num_questions": "2", "difficulty": "medium", "question_type": "mcq"},
                   files={"file": ("photosynthesis.txt", txt.encode("utf-8"), "text/plain")}, headers=teacher)
        check("generate MCQ from TXT", r.status_code == 200 and r.json()["count"] >= 1 and r.json()["source_chars"] > 200, (r.status_code, r.text[:160]))

        from docx import Document
        d = Document()
        d.add_paragraph("Ohm's law states that the current through a conductor between two points is directly proportional to the voltage across the two points.")
        d.add_paragraph("The constant of proportionality is the resistance: V = I x R. Resistance is measured in ohms, current in amperes and voltage in volts.")
        d.add_paragraph("Resistors in series add up, while for resistors in parallel the reciprocals add up.")
        buf = io.BytesIO()
        d.save(buf)
        r = c.post(f"{BASE}/quizzes/generate-from-document", data={"num_questions": "2", "difficulty": "easy", "question_type": "mixed", "subject": "Physics"},
                   files={"file": ("ohm.docx", buf.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}, headers=teacher)
        check("generate mixed questions from DOCX", r.status_code == 200 and r.json()["count"] >= 1, (r.status_code, r.text[:160]))

        r = c.post(f"{BASE}/quizzes/generate-from-document", data={"num_questions": "2"},
                   files={"file": ("old.doc", b"xx", "application/msword")}, headers=teacher)
        check("unsupported .doc rejected (400)", r.status_code == 400, r.json().get("detail"))

    # ── summary / cleanup ────────────────────────────────────────────────────
    failed = [n for n, ok, _ in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if args.drop:
        mongo.drop_database(args.db)
        print(f"dropped database {args.db}")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
