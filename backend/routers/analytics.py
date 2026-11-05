"""
Analytics & Monitoring API endpoints (Module 12).
Provides student analytics, performance prediction, class analytics, and suspicious behavior detection.
"""
from fastapi import APIRouter, Depends, HTTPException
from bson import ObjectId
from database import get_db
from routers.deps import get_current_user, get_current_teacher, get_current_student
from services.analytics_helpers import score_buckets, weak_questions
from services.monitoring import (
    get_student_analytics,
    predict_performance,
    get_class_analytics,
    detect_suspicious_behavior,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


async def _assert_class_owned(db, class_id: str, teacher_id: str) -> dict:
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")
    cls = await db["classes"].find_one({"_id": ObjectId(class_id), "teacher_id": teacher_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")
    return cls


async def _assert_teacher_can_view_student(db, teacher_id: str, student_id: str) -> None:
    """A teacher may only look at students enrolled in one of their own classes."""
    classes = await db["classes"].find({"teacher_id": teacher_id}, {"_id": 1}).to_list(length=500)
    class_ids = [str(c["_id"]) for c in classes]
    enrolled = None
    if class_ids:
        enrolled = await db["enrollments"].find_one({"student_id": student_id, "class_id": {"$in": class_ids}})
    if not enrolled:
        raise HTTPException(status_code=404, detail="Student not found in your classes")


@router.get("/student/me")
async def my_analytics(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student views their own performance analytics."""
    return await get_student_analytics(db, current_student["id"])


# Declared BEFORE /student/{student_id}: otherwise 'deadlines' is taken as a student id
# and students get a 403 from the teacher-only route.
@router.get("/student/deadlines")
async def student_deadlines(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """
    Aggregate all assignments, quizzes, and OMR templates across the student's
    enrolled classes with status (open / completed / closed) and time remaining.
    """
    from datetime import datetime
    student_id = current_student["id"]

    # Enrolled classes
    enrollments = await db["enrollments"].find({"student_id": student_id}).to_list(length=200)
    class_ids = [e["class_id"] for e in enrollments]
    if not class_ids:
        return {"items": [], "stats": {"open": 0, "completed": 0, "closed": 0, "total": 0}}

    # Fetch class names
    valid_oids = [ObjectId(c) for c in class_ids if ObjectId.is_valid(c)]
    classes = await db["classes"].find({"_id": {"$in": valid_oids}}).to_list(length=200) if valid_oids else []
    class_name_map = {str(c["_id"]): c.get("name", "") for c in classes}

    # Assignments
    assignments = await db["assignments"].find({"class_id": {"$in": class_ids}}).to_list(length=500)
    assignment_ids = [str(a["_id"]) for a in assignments]
    my_subs = []
    if assignment_ids:
        my_subs = await db["submissions"].find({
            "student_id": student_id,
            "assignment_id": {"$in": assignment_ids},
        }).to_list(length=500)
    submitted_assignments = {s["assignment_id"] for s in my_subs}

    # Quizzes
    quizzes = await db["quizzes"].find({"class_id": {"$in": class_ids}}).to_list(length=500)
    quiz_ids = [str(q["_id"]) for q in quizzes]
    my_attempts = []
    if quiz_ids:
        my_attempts = await db["quiz_attempts"].find({
            "student_id": student_id,
            "quiz_id": {"$in": quiz_ids},
        }).to_list(length=500)
    attempted_quizzes = {a["quiz_id"] for a in my_attempts}

    # OMR templates
    omr_templates = await db["omr_templates"].find({"class_id": {"$in": class_ids}}).to_list(length=500)
    omr_template_ids = [str(t["_id"]) for t in omr_templates]
    my_omr_subs = []
    if omr_template_ids:
        my_omr_subs = await db["omr_submissions"].find({
            "submitter_id": student_id,
            "submitter_role": "student",
            "template_id": {"$in": omr_template_ids},
        }).to_list(length=500)
    submitted_omr = {s["template_id"] for s in my_omr_subs}

    now = datetime.utcnow()
    items = []

    def classify(deadline, completed):
        if completed:
            return "completed"
        if deadline and deadline < now:
            return "closed"
        return "open"

    def time_remaining_seconds(deadline):
        if not deadline:
            return None
        delta = (deadline - now).total_seconds()
        return int(delta)

    for a in assignments:
        a_id = str(a["_id"])
        completed = a_id in submitted_assignments
        items.append({
            "type": "assignment",
            "id": a_id,
            "title": a.get("title", ""),
            "class_id": a.get("class_id"),
            "class_name": class_name_map.get(a.get("class_id", ""), ""),
            "deadline": a["deadline"].isoformat() if a.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(a.get("deadline")),
            "status": classify(a.get("deadline"), completed),
            "total_marks": a.get("total_marks", 0),
        })

    for q in quizzes:
        q_id = str(q["_id"])
        completed = q_id in attempted_quizzes
        items.append({
            "type": "quiz",
            "id": q_id,
            "title": q.get("title", ""),
            "class_id": q.get("class_id"),
            "class_name": class_name_map.get(q.get("class_id", ""), ""),
            "deadline": q["deadline"].isoformat() if q.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(q.get("deadline")),
            "status": classify(q.get("deadline"), completed),
            "total_marks": q.get("total_marks", 0),
            "time_limit_minutes": q.get("time_limit_minutes"),
        })

    for t in omr_templates:
        t_id = str(t["_id"])
        completed = t_id in submitted_omr
        items.append({
            "type": "omr",
            "id": t_id,
            "title": t.get("title", ""),
            "class_id": t.get("class_id"),
            "class_name": class_name_map.get(t.get("class_id", ""), ""),
            "deadline": t["deadline"].isoformat() if t.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(t.get("deadline")),
            "status": classify(t.get("deadline"), completed),
            "total_marks": t.get("total_marks", 0),
        })

    # Sort: open first by closest deadline, then completed, then closed
    def sort_key(it):
        order = {"open": 0, "completed": 1, "closed": 2}[it["status"]]
        # No deadline → put after dated ones within same status
        tr = it["time_remaining_seconds"]
        return (order, tr if tr is not None else 999_999_999)

    items.sort(key=sort_key)

    stats = {
        "total": len(items),
        "open": sum(1 for i in items if i["status"] == "open"),
        "completed": sum(1 for i in items if i["status"] == "completed"),
        "closed": sum(1 for i in items if i["status"] == "closed"),
    }

    return {"items": items, "stats": stats}


@router.get("/student/{student_id}")
async def student_analytics(
    student_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher views a specific student's analytics."""
    await _assert_teacher_can_view_student(db, current_teacher["id"], student_id)
    return await get_student_analytics(db, student_id)


@router.get("/predict/me")
async def my_prediction(
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student views their performance prediction."""
    return await predict_performance(db, current_student["id"])


@router.get("/predict/{student_id}")
async def student_prediction(
    student_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher views a student's performance prediction."""
    await _assert_teacher_can_view_student(db, current_teacher["id"], student_id)
    return await predict_performance(db, student_id)


@router.get("/class/{class_id}")
async def class_analytics(
    class_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher views analytics for an entire class."""
    await _assert_class_owned(db, class_id, current_teacher["id"])
    return await get_class_analytics(db, class_id)


@router.get("/alerts/{student_id}")
async def student_alerts(
    student_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher checks for suspicious behavior from a student."""
    await _assert_teacher_can_view_student(db, current_teacher["id"], student_id)
    return await detect_suspicious_behavior(db, student_id)


@router.get("/teacher/deadlines")
async def teacher_deadlines(
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Aggregate all assignments, quizzes, and OMR templates owned by this teacher
    with submission counts and time remaining.
    """
    from datetime import datetime
    teacher_id = current_teacher["id"]

    classes = await db["classes"].find({"teacher_id": teacher_id}).to_list(length=200)
    class_ids = [str(c["_id"]) for c in classes]
    class_name_map = {str(c["_id"]): c.get("name", "") for c in classes}

    # Enrollment counts per class
    enrollment_counts = {}
    if class_ids:
        for cid in class_ids:
            enrollment_counts[cid] = await db["enrollments"].count_documents({"class_id": cid})

    assignments = await db["assignments"].find({"teacher_id": teacher_id}).to_list(length=500)
    assignment_ids = [str(a["_id"]) for a in assignments]

    # Per-assignment submission counts
    sub_counts = {}
    if assignment_ids:
        cursor = db["submissions"].aggregate([
            {"$match": {"assignment_id": {"$in": assignment_ids}}},
            {"$group": {"_id": "$assignment_id", "count": {"$sum": 1}}},
        ])
        sub_counts = {doc["_id"]: doc["count"] async for doc in cursor}

    # Quizzes
    quizzes = []
    quiz_ids = []
    if class_ids:
        quizzes = await db["quizzes"].find({"class_id": {"$in": class_ids}}).to_list(length=500)
        quiz_ids = [str(q["_id"]) for q in quizzes]
    attempt_counts = {}
    if quiz_ids:
        cursor = db["quiz_attempts"].aggregate([
            {"$match": {"quiz_id": {"$in": quiz_ids}}},
            {"$group": {"_id": "$quiz_id", "count": {"$sum": 1}}},
        ])
        attempt_counts = {doc["_id"]: doc["count"] async for doc in cursor}

    # OMR
    omr_templates = await db["omr_templates"].find({"teacher_id": teacher_id}).to_list(length=500)
    omr_ids = [str(t["_id"]) for t in omr_templates]
    omr_counts = {}
    if omr_ids:
        cursor = db["omr_submissions"].aggregate([
            {"$match": {"template_id": {"$in": omr_ids}}},
            {"$group": {"_id": "$template_id", "count": {"$sum": 1}}},
        ])
        omr_counts = {doc["_id"]: doc["count"] async for doc in cursor}

    now = datetime.utcnow()
    items = []

    def classify(deadline):
        if deadline and deadline < now:
            return "closed"
        return "open"

    def time_remaining_seconds(deadline):
        if not deadline:
            return None
        return int((deadline - now).total_seconds())

    for a in assignments:
        a_id = str(a["_id"])
        cid = a.get("class_id", "")
        enrolled = enrollment_counts.get(cid, 0)
        submitted = sub_counts.get(a_id, 0)
        items.append({
            "type": "assignment",
            "id": a_id,
            "title": a.get("title", ""),
            "class_id": cid,
            "class_name": class_name_map.get(cid, ""),
            "deadline": a["deadline"].isoformat() if a.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(a.get("deadline")),
            "status": classify(a.get("deadline")),
            "submitted_count": submitted,
            "enrolled_count": enrolled,
            "submission_rate": round((submitted / enrolled) * 100, 1) if enrolled > 0 else 0,
            "total_marks": a.get("total_marks", 0),
        })

    for q in quizzes:
        q_id = str(q["_id"])
        cid = q.get("class_id", "")
        enrolled = enrollment_counts.get(cid, 0)
        attempted = attempt_counts.get(q_id, 0)
        items.append({
            "type": "quiz",
            "id": q_id,
            "title": q.get("title", ""),
            "class_id": cid,
            "class_name": class_name_map.get(cid, ""),
            "deadline": q["deadline"].isoformat() if q.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(q.get("deadline")),
            "status": classify(q.get("deadline")),
            "submitted_count": attempted,
            "enrolled_count": enrolled,
            "submission_rate": round((attempted / enrolled) * 100, 1) if enrolled > 0 else 0,
            "total_marks": q.get("total_marks", 0),
            "time_limit_minutes": q.get("time_limit_minutes"),
        })

    for t in omr_templates:
        t_id = str(t["_id"])
        cid = t.get("class_id", "")
        enrolled = enrollment_counts.get(cid, 0)
        submitted = omr_counts.get(t_id, 0)
        items.append({
            "type": "omr",
            "id": t_id,
            "title": t.get("title", ""),
            "class_id": cid,
            "class_name": class_name_map.get(cid, ""),
            "deadline": t["deadline"].isoformat() if t.get("deadline") else None,
            "time_remaining_seconds": time_remaining_seconds(t.get("deadline")),
            "status": classify(t.get("deadline")),
            "submitted_count": submitted,
            "enrolled_count": enrolled,
            "submission_rate": round((submitted / enrolled) * 100, 1) if enrolled > 0 else 0,
            "total_marks": t.get("total_marks", 0),
        })

    items.sort(key=lambda i: (
        i["status"] == "closed",
        i["time_remaining_seconds"] if i["time_remaining_seconds"] is not None else 999_999_999,
    ))

    stats = {
        "total": len(items),
        "open": sum(1 for i in items if i["status"] == "open"),
        "closed": sum(1 for i in items if i["status"] == "closed"),
    }

    return {"items": items, "stats": stats}


@router.get("/teacher/overview")
async def teacher_overview(
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Unified analytics for the teacher across ALL their classes:
    submission stats, quiz stats, OMR stats, class averages, performance trends.
    """
    teacher_id = current_teacher["id"]

    # Classes
    classes = await db["classes"].find({"teacher_id": teacher_id}).to_list(length=200)
    class_ids = [str(c["_id"]) for c in classes]

    # Assignments (used to scope submissions)
    assignments = await db["assignments"].find({"teacher_id": teacher_id}).to_list(length=500)
    assignment_ids = [str(a["_id"]) for a in assignments]

    # Submissions
    submissions = []
    if assignment_ids:
        submissions = await db["submissions"].find({"assignment_id": {"$in": assignment_ids}}).to_list(length=2000)

    graded_subs = [s for s in submissions if s.get("status") == "graded" and s.get("score") is not None]
    sub_scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in graded_subs]

    # Quizzes
    quizzes = []
    if class_ids:
        quizzes = await db["quizzes"].find({"class_id": {"$in": class_ids}}).to_list(length=500)
    quiz_ids = [str(q["_id"]) for q in quizzes]
    quiz_attempts = []
    if quiz_ids:
        quiz_attempts = await db["quiz_attempts"].find({"quiz_id": {"$in": quiz_ids}}).to_list(length=2000)
    quiz_scores = [(a["score"] / max(a.get("total_marks", 1), 1)) * 100 for a in quiz_attempts]

    # OMR
    omr_templates = await db["omr_templates"].find({"teacher_id": teacher_id}).to_list(length=500)
    omr_template_ids = [str(t["_id"]) for t in omr_templates]
    omr_subs = []
    if omr_template_ids:
        omr_subs = await db["omr_submissions"].find({"template_id": {"$in": omr_template_ids}}).to_list(length=2000)
    omr_graded = [s for s in omr_subs if s.get("status") == "graded" and s.get("score") is not None]
    omr_scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in omr_graded]

    # Total enrolled students across all classes (unique)
    enrollments = []
    if class_ids:
        enrollments = await db["enrollments"].find({"class_id": {"$in": class_ids}}).to_list(length=1000)
    unique_students = len({e["student_id"] for e in enrollments})

    # Per-class averages
    class_averages = []
    for c in classes:
        cid = str(c["_id"])
        c_assignments = [a for a in assignments if a["class_id"] == cid]
        c_assign_ids = [str(a["_id"]) for a in c_assignments]
        c_subs_graded = [s for s in graded_subs if s["assignment_id"] in c_assign_ids]
        c_scores = [(s["score"] / max(s.get("total_marks", 1), 1)) * 100 for s in c_subs_graded]
        c_quiz_ids = {str(q["_id"]) for q in quizzes if q.get("class_id") == cid}
        c_quiz_scores = [(a["score"] / max(a.get("total_marks", 1), 1)) * 100 for a in quiz_attempts if a.get("quiz_id") in c_quiz_ids]
        class_averages.append({
            "class_id": cid,
            "class_name": c.get("name", ""),
            "enrolled": sum(1 for e in enrollments if e["class_id"] == cid),
            "assignments": len(c_assignments),
            "submissions": len(c_subs_graded),
            "average_score": round(sum(c_scores) / len(c_scores), 1) if c_scores else None,
            "quizzes": len(c_quiz_ids),
            "quiz_attempts": len(c_quiz_scores),
            "quiz_average": round(sum(c_quiz_scores) / len(c_quiz_scores), 1) if c_quiz_scores else None,
        })

    # Plagiarism flags (from submissions where similarity_max > 0.3)
    flagged_subs = [s for s in submissions if (s.get("similarity_max") or 0) >= 0.3]

    # Submission timeline (counts per day, last 14 days)
    from datetime import datetime, timedelta
    now = datetime.utcnow()
    timeline = []
    for i in range(13, -1, -1):
        d = (now - timedelta(days=i)).date()
        d_start = datetime.combine(d, datetime.min.time())
        d_end = d_start + timedelta(days=1)
        count = sum(1 for s in submissions if s.get("created_at") and d_start <= s["created_at"] < d_end)
        timeline.append({
            "date": d.isoformat(),
            "submissions": count,
        })

    return {
        "totals": {
            "classes": len(classes),
            "students": unique_students,
            "assignments": len(assignments),
            "submissions": len(submissions),
            "graded_submissions": len(graded_subs),
            "quizzes": len(quizzes),
            "quiz_attempts": len(quiz_attempts),
            "omr_templates": len(omr_templates),
            "omr_submissions": len(omr_subs),
            "plagiarism_flags": len(flagged_subs),
        },
        "averages": {
            "submission_avg": round(sum(sub_scores) / len(sub_scores), 1) if sub_scores else None,
            "quiz_avg": round(sum(quiz_scores) / len(quiz_scores), 1) if quiz_scores else None,
            "omr_avg": round(sum(omr_scores) / len(omr_scores), 1) if omr_scores else None,
        },
        "class_averages": class_averages,
        "submission_timeline": timeline,
        # How scores spread (grade bands) and which quiz questions most students get wrong.
        "score_distribution": {
            "submissions": score_buckets(sub_scores),
            "quizzes": score_buckets(quiz_scores),
            "omr": score_buckets(omr_scores),
        },
        "weak_questions": weak_questions(quizzes, quiz_attempts, limit=8),
    }
