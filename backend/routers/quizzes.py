"""
Quiz Router — Teacher creates MCQ / true-false quizzes (manually or via AI, optionally from
an uploaded PDF, TXT or DOCX), students take them once with a server-timed window, both see results.
"""
import random
from datetime import datetime, timedelta
from typing import List, Optional, Union
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Form
from pydantic import BaseModel
from bson import ObjectId

from core.timeutil import parse_deadline
from database import get_db
from models.school import QuizOut, QuizAttemptOut
from routers.deps import get_current_teacher, get_current_student, get_current_user
from services.document_text import DocumentError, SUPPORTED_EXTENSIONS, extract_text
from services.quiz_generator import GenerationError, QUESTION_TYPES as GENERATION_TYPES, generate_quiz_questions
from services.audit import AuditError, record_audit
from services.quiz_logic import QuizValidationError, coerce_answers, is_correct, normalise_question, submission_window
from services.quiz_logic import validate_questions as validate_question_dicts
from services.notifications import notify_user

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


# ── Request bodies ──────────────────────────────────────────────────────────
class QuizQuestionInput(BaseModel):
    type: str = "mcq"  # mcq | true_false | short_answer
    question_text: str
    options: List[str] = []                       # mcq / true_false
    correct_index: Optional[int] = None           # mcq / true_false
    accepted_answers: Optional[List[str]] = None  # short_answer: any of these (case/punctuation-insensitive)
    marks: int = 1
    explanation: Optional[str] = None


class QuizCreateBody(BaseModel):
    class_id: str
    title: str
    description: Optional[str] = None
    questions: List[QuizQuestionInput]
    time_limit_minutes: int = 30
    deadline: Optional[str] = None
    shuffle_questions: bool = True
    shuffle_options: bool = True
    show_correct_after: bool = True


class AttemptResetBody(BaseModel):
    reason: str


class QuizUpdateBody(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    questions: Optional[List[QuizQuestionInput]] = None
    time_limit_minutes: Optional[int] = None
    deadline: Optional[str] = None
    shuffle_questions: Optional[bool] = None
    shuffle_options: Optional[bool] = None
    show_correct_after: Optional[bool] = None


class QuizGenerateBody(BaseModel):
    topic: str
    num_questions: int = 5
    difficulty: str = "medium"
    source_text: Optional[str] = None
    question_type: str = "mcq"  # mcq | true_false | mixed
    grade_level: Optional[str] = None
    subject: Optional[str] = None
    objectives: Optional[str] = None


class QuizSubmitBody(BaseModel):
    answers: List[Union[int, str, None]]  # option index per choice question, text per short answer
    started_at: Optional[str] = None  # ignored: the server recorded the start in /start
    auto_submitted: bool = False
    # Integrity / proctoring metrics
    tab_switches: int = 0
    time_away_seconds: int = 0
    copy_attempts: int = 0
    paste_attempts: int = 0


# ── Helpers ─────────────────────────────────────────────────────────────────
def _validate_questions(questions: List[QuizQuestionInput]) -> int:
    """Validate MCQ / true-false questions and return total_marks (rules in services/quiz_logic.py)."""
    try:
        # Validate what the client actually sent (a true/false question with three options is
        # a client bug); normalise_question() then fixes option texts for storage.
        return validate_question_dicts([q.model_dump() for q in questions])
    except QuizValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _generation_type(value: str) -> str:
    value = (value or "mcq").strip().lower()
    if value not in GENERATION_TYPES:
        raise HTTPException(status_code=400, detail=f"question_type must be one of {', '.join(GENERATION_TYPES)}")
    return value


def _parse_deadline(deadline: Optional[str]) -> Optional[datetime]:
    if not deadline or not deadline.strip():
        return None
    try:
        parsed = parse_deadline(deadline)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid deadline format")
    # Block deadlines that are already in the past at creation/edit time.
    if parsed < datetime.utcnow():
        raise HTTPException(status_code=400, detail="Deadline cannot be in the past")
    return parsed


def _map_quiz(doc: dict, hide_answers: bool = False) -> dict:
    """Map MongoDB doc to QuizOut format. Optionally hide correct answers."""
    out = dict(doc)
    out["quiz_id"] = str(doc["_id"])
    out["question_count"] = len(doc.get("questions", []))
    if hide_answers and "questions" in out:
        out["questions"] = [
            {
                "type": q.get("type", "mcq"),
                "question_text": q["question_text"],
                "options": q["options"],
                "marks": q.get("marks", 1),
            }
            for q in out["questions"]
        ]
    return out


async def _verify_class_owned_by_teacher(db, class_id: str, teacher_id: str):
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")
    cls = await db["classes"].find_one({"_id": ObjectId(class_id), "teacher_id": teacher_id})
    if not cls:
        raise HTTPException(status_code=404, detail="Class not found")


# ── AI Generation ───────────────────────────────────────────────────────────
@router.post("/generate")
async def generate_quiz(
    body: QuizGenerateBody,
    current_teacher: dict = Depends(get_current_teacher),
):
    """Teacher uses AI to generate MCQ / true-false questions on a topic. Returns draft questions to review."""
    if not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")
    try:
        questions = await generate_quiz_questions(
            topic=body.topic,
            num_questions=body.num_questions,
            difficulty=body.difficulty,
            source_text=body.source_text,
            question_type=_generation_type(body.question_type),
            grade_level=body.grade_level,
            subject=body.subject,
            objectives=body.objectives,
        )
    except GenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not questions:
        raise HTTPException(status_code=502, detail="AI did not return any valid questions. Try again or refine the topic.")
    return {"questions": questions, "count": len(questions)}


@router.post("/generate-from-document")
@router.post("/generate-from-pdf")  # old name, kept for existing clients
async def generate_quiz_from_document(
    file: UploadFile = File(...),
    topic: Optional[str] = Form(None),
    num_questions: int = Form(5),
    difficulty: str = Form("medium"),
    question_type: str = Form("mcq"),
    grade_level: Optional[str] = Form(None),
    subject: Optional[str] = Form(None),
    objectives: Optional[str] = Form(None),
    current_teacher: dict = Depends(get_current_teacher),
):
    """
    Teacher uploads reference material (PDF, TXT, MD or DOCX); the server extracts its
    text and generates questions grounded in that content.
    """
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")
    if len(data) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="File too large (limit: 15 MB).")

    try:
        source_text = extract_text(file.filename or "", data)
    except DocumentError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if len(source_text) < 200:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not extract enough text from the file. PDFs must contain selectable text "
                "(scanned or handwritten PDFs are not supported here); TXT and DOCX files work as they are."
            ),
        )

    derived_topic = (topic or "").strip() or (file.filename or "document").rsplit(".", 1)[0]

    try:
        questions = await generate_quiz_questions(
            topic=derived_topic,
            num_questions=num_questions,
            difficulty=difficulty,
            source_text=source_text,
            question_type=_generation_type(question_type),
            grade_level=grade_level,
            subject=subject,
            objectives=objectives,
        )
    except GenerationError as e:
        raise HTTPException(status_code=502, detail=str(e))
    if not questions:
        raise HTTPException(status_code=502, detail="AI did not return any valid questions. Try again.")
    return {
        "questions": questions,
        "count": len(questions),
        "topic": derived_topic,
        "source_chars": len(source_text),
        "supported_types": list(SUPPORTED_EXTENSIONS),
    }


# ── CRUD ────────────────────────────────────────────────────────────────────
@router.post("/", response_model=QuizOut)
async def create_quiz(
    body: QuizCreateBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Create a new quiz from manually-crafted or AI-generated questions."""
    await _verify_class_owned_by_teacher(db, body.class_id, current_teacher["id"])

    total_marks = _validate_questions(body.questions)
    deadline = _parse_deadline(body.deadline)

    if body.time_limit_minutes < 1:
        raise HTTPException(status_code=400, detail="Time limit must be at least 1 minute")

    record = {
        "class_id": body.class_id,
        "teacher_id": current_teacher["id"],
        "title": body.title.strip(),
        "description": body.description.strip() if body.description else None,
        "questions": [normalise_question(q) for q in body.questions],
        "total_marks": total_marks,
        "time_limit_minutes": body.time_limit_minutes,
        "deadline": deadline,
        "shuffle_questions": body.shuffle_questions,
        "shuffle_options": body.shuffle_options,
        "show_correct_after": body.show_correct_after,
        "created_at": datetime.utcnow(),
    }
    result = await db["quizzes"].insert_one(record)
    record["_id"] = result.inserted_id

    # Notify enrolled students
    cls = await db["classes"].find_one({"_id": ObjectId(body.class_id)})
    enrolled = await db["enrollments"].find({"class_id": body.class_id}).to_list(length=500)
    for enr in enrolled:
        await notify_user(
            db,
            user_id=enr["student_id"],
            title="New quiz available",
            body=f"'{body.title}' in {cls.get('name', 'your class') if cls else 'your class'} ({body.time_limit_minutes} min)",
            link="/",
            category="quiz",
        )

    return _map_quiz(record)


@router.get("/class/{class_id}", response_model=List[QuizOut])
async def list_class_quizzes(
    class_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """List quizzes for a class. Students must be enrolled."""
    if not ObjectId.is_valid(class_id):
        raise HTTPException(status_code=400, detail="Invalid class_id")

    if current_user["role"] == "student":
        enr = await db["enrollments"].find_one({
            "class_id": class_id, "student_id": current_user["id"]
        })
        if not enr:
            raise HTTPException(status_code=403, detail="Enroll in this class to view quizzes")

    cursor = db["quizzes"].find({"class_id": class_id}).sort("created_at", -1)
    quizzes = await cursor.to_list(length=200)

    result = []
    for q in quizzes:
        # Hide answers for students; show for teachers
        is_student = current_user["role"] == "student"
        mapped = _map_quiz(q, hide_answers=is_student)
        if is_student:
            # Don't even send questions list — just metadata
            mapped.pop("questions", None)
            attempt = await db["quiz_attempts"].find_one({
                "quiz_id": mapped["quiz_id"], "student_id": current_user["id"]
            })
            mapped["has_attempted"] = attempt is not None
        else:
            mapped["attempt_count"] = await db["quiz_attempts"].count_documents({
                "quiz_id": mapped["quiz_id"]
            })
        result.append(mapped)
    return result


@router.get("/{quiz_id}", response_model=QuizOut)
async def get_quiz(
    quiz_id: str,
    current_user: dict = Depends(get_current_user),
    db=Depends(get_db),
):
    """Get a quiz. Teachers see full data; students see questions WITHOUT correct answers."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    if current_user["role"] == "student":
        enr = await db["enrollments"].find_one({
            "class_id": quiz["class_id"], "student_id": current_user["id"]
        })
        if not enr:
            raise HTTPException(status_code=403, detail="Enroll in this class to view quizzes")

    is_student = current_user["role"] == "student"
    return _map_quiz(quiz, hide_answers=is_student)


@router.patch("/{quiz_id}", response_model=QuizOut)
async def update_quiz(
    quiz_id: str,
    body: QuizUpdateBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Edit a quiz."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")

    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id), "teacher_id": current_teacher["id"]})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    updates = {}
    if body.title is not None:
        updates["title"] = body.title.strip()
    if body.description is not None:
        updates["description"] = body.description.strip() or None
    if body.questions is not None:
        # The answer key is locked once anyone has attempted the quiz (the UI hides this too).
        if await db["quiz_attempts"].count_documents({"quiz_id": quiz_id}) > 0:
            raise HTTPException(status_code=409, detail="Questions are locked once a student has attempted the quiz")
        updates["total_marks"] = _validate_questions(body.questions)
        updates["questions"] = [normalise_question(q) for q in body.questions]
    if body.time_limit_minutes is not None:
        if body.time_limit_minutes < 1:
            raise HTTPException(status_code=400, detail="Time limit must be at least 1 minute")
        updates["time_limit_minutes"] = body.time_limit_minutes
    if body.deadline is not None:
        updates["deadline"] = _parse_deadline(body.deadline)
    if body.shuffle_questions is not None:
        updates["shuffle_questions"] = body.shuffle_questions
    if body.shuffle_options is not None:
        updates["shuffle_options"] = body.shuffle_options
    if body.show_correct_after is not None:
        updates["show_correct_after"] = body.show_correct_after

    if updates:
        await db["quizzes"].update_one({"_id": ObjectId(quiz_id)}, {"$set": updates})

    updated = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})

    # Notify enrolled students if deadline or time_limit changed
    if "deadline" in updates or "time_limit_minutes" in updates:
        cls = await db["classes"].find_one({"_id": ObjectId(quiz["class_id"])}) if ObjectId.is_valid(quiz["class_id"]) else None
        enrolled = await db["enrollments"].find({"class_id": quiz["class_id"]}).to_list(length=500)
        bits = []
        if "deadline" in updates:
            new_dl = updates["deadline"]
            bits.append(f"new deadline {new_dl.strftime('%Y-%m-%d %H:%M')}" if new_dl else "deadline removed")
        if "time_limit_minutes" in updates:
            bits.append(f"time limit {updates['time_limit_minutes']} min")
        for enr in enrolled:
            await notify_user(
                db,
                user_id=enr["student_id"],
                title="Quiz updated",
                body=f"'{updated.get('title')}' in {cls.get('name') if cls else 'your class'} — {', '.join(bits)}",
                link="/",
                category="quiz",
            )

    return _map_quiz(updated)


@router.delete("/{quiz_id}", status_code=204)
async def delete_quiz(
    quiz_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Delete a quiz and all its attempts."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id), "teacher_id": current_teacher["id"]})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    await db["quiz_attempts"].delete_many({"quiz_id": quiz_id})
    await db["quiz_sessions"].delete_many({"quiz_id": quiz_id})
    await db["quizzes"].delete_one({"_id": ObjectId(quiz_id)})


# ── Take Quiz (Student) ─────────────────────────────────────────────────────
@router.post("/{quiz_id}/start")
async def start_quiz(
    quiz_id: str,
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """
    Student begins a quiz attempt. Returns the quiz with questions
    (shuffled if enabled) and the server-side started_at timestamp.
    Cannot retake.
    """
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Verify enrollment
    enr = await db["enrollments"].find_one({
        "class_id": quiz["class_id"], "student_id": current_student["id"]
    })
    if not enr:
        raise HTTPException(status_code=403, detail="Enroll in this class first")

    # Check deadline
    if quiz.get("deadline") and datetime.utcnow() > quiz["deadline"]:
        raise HTTPException(status_code=403, detail="Quiz deadline has passed")

    # Check if already attempted
    existing = await db["quiz_attempts"].find_one({
        "quiz_id": quiz_id, "student_id": current_student["id"]
    })
    if existing:
        raise HTTPException(status_code=409, detail="You have already taken this quiz")

    # The start time is recorded on the SERVER: reopening the page keeps the same clock,
    # and /submit measures the time limit from this timestamp, not from the client.
    # Millisecond precision: MongoDB stores no microseconds, and the value must read back
    # identical so a refresh gets the same clock and the same shuffle seed.
    now = datetime.utcnow().replace(microsecond=(datetime.utcnow().microsecond // 1000) * 1000)
    session = await db["quiz_sessions"].find_one({"quiz_id": quiz_id, "student_id": current_student["id"]})
    if session:
        started_at = session["started_at"]
    else:
        started_at = now
        await db["quiz_sessions"].insert_one({
            "quiz_id": quiz_id, "student_id": current_student["id"], "started_at": started_at,
        })
    window = submission_window(quiz, started_at, now)
    if not window["open"]:
        raise HTTPException(status_code=403, detail="Your time for this quiz has run out")

    # Build student-safe view with optional shuffling. The shuffle is seeded with the
    # session so a page refresh shows the same order and autosaved answers still line up.
    rng = random.Random(f"{quiz_id}:{current_student['id']}:{started_at.isoformat()}")
    questions = list(quiz["questions"])
    # Track original indices so we can grade correctly after shuffle
    indexed = [{"_orig_idx": i, **q} for i, q in enumerate(questions)]

    if quiz.get("shuffle_questions"):
        rng.shuffle(indexed)

    safe_questions = []
    for q in indexed:
        opts = list(q["options"])
        # Track which option is which after shuffle
        option_pairs = list(enumerate(opts))
        if quiz.get("shuffle_options") and q.get("type", "mcq") != "true_false":
            rng.shuffle(option_pairs)
        # Build mapping: original_option_idx -> shuffled_position
        shuffled_options = [pair[1] for pair in option_pairs]
        # We send: position-mapping so we can decode answers later
        # But to keep it stateless, we just send shuffled options & track on submit
        safe_questions.append({
            "type": q.get("type", "mcq"),
            "question_text": q["question_text"],
            "options": shuffled_options,
            "marks": q.get("marks", 1),
            # Send mapping so client can return answers in original frame
            "_orig_idx": q["_orig_idx"],
            "_option_map": [pair[0] for pair in option_pairs],  # pos i in shuffled → original idx
        })

    return {
        "quiz_id": quiz_id,
        "title": quiz["title"],
        "description": quiz.get("description"),
        "questions": safe_questions,
        "total_marks": quiz["total_marks"],
        "time_limit_minutes": quiz["time_limit_minutes"],
        "started_at": started_at.isoformat(),
        "ends_at": window["ends_at"].isoformat(),
        "seconds_left": max(0, int((window["ends_at"] - now).total_seconds())),
        "deadline": quiz["deadline"].isoformat() if quiz.get("deadline") else None,
    }


@router.post("/{quiz_id}/submit", response_model=QuizAttemptOut)
async def submit_quiz(
    quiz_id: str,
    body: QuizSubmitBody,
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """
    Submit quiz answers. Body.answers is a list of selected option indices
    in ORIGINAL question/option order (frontend converts back using _option_map).
    """
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    # Verify enrollment
    enr = await db["enrollments"].find_one({
        "class_id": quiz["class_id"], "student_id": current_student["id"]
    })
    if not enr:
        raise HTTPException(status_code=403, detail="Enroll in this class first")

    # Check duplicate attempt
    existing = await db["quiz_attempts"].find_one({
        "quiz_id": quiz_id, "student_id": current_student["id"]
    })
    if existing:
        raise HTTPException(status_code=409, detail="Already submitted")

    # Enforce the time limit and the deadline from the server-side start time.
    submitted_at = datetime.utcnow()
    session = await db["quiz_sessions"].find_one({"quiz_id": quiz_id, "student_id": current_student["id"]})
    if not session:
        raise HTTPException(status_code=409, detail="Start the quiz before submitting it")
    started_at = session["started_at"]
    window = submission_window(quiz, started_at, submitted_at)
    if not window["open"]:
        why = "the deadline has passed" if window["reason"] == "deadline" else "the time limit has run out"
        raise HTTPException(status_code=403, detail=f"Submission refused: {why}")
    time_taken = max(0, int((submitted_at - started_at).total_seconds()))

    questions = quiz["questions"]
    try:
        answers = coerce_answers(questions, list(body.answers))
    except QuizValidationError as e:
        raise HTTPException(status_code=400, detail=str(e))

    # Grade (choice questions by index, short answers by normalised text match)
    score = 0
    correct_count = 0
    for q, ans in zip(questions, answers):
        if is_correct(q, ans):
            score += q.get("marks", 1)
            correct_count += 1

    record = {
        "quiz_id": quiz_id,
        "student_id": current_student["id"],
        "status": "submitted",
        "late_by_seconds": window["late_by_seconds"],
        "answers": answers,
        "score": score,
        "total_marks": quiz["total_marks"],
        "correct_count": correct_count,
        "started_at": started_at,
        "submitted_at": submitted_at,
        "time_taken_seconds": time_taken,
        "auto_submitted": body.auto_submitted,
        "tab_switches": max(0, int(body.tab_switches or 0)),
        "time_away_seconds": max(0, int(body.time_away_seconds or 0)),
        "copy_attempts": max(0, int(body.copy_attempts or 0)),
        "paste_attempts": max(0, int(body.paste_attempts or 0)),
    }
    result = await db["quiz_attempts"].insert_one(record)
    await db["quiz_sessions"].delete_one({"quiz_id": quiz_id, "student_id": current_student["id"]})

    # Notify teacher of quiz attempt
    integrity_flags = []
    if record["tab_switches"] > 0:
        integrity_flags.append(f"{record['tab_switches']} tab switch(es)")
    if record["paste_attempts"] > 0:
        integrity_flags.append(f"{record['paste_attempts']} paste attempt(s)")
    integrity_note = f" ⚠ {', '.join(integrity_flags)}" if integrity_flags else ""

    await notify_user(
        db,
        user_id=quiz["teacher_id"],
        title="Quiz attempt submitted",
        body=f"{current_student.get('name', 'A student')} scored {score}/{quiz['total_marks']} on '{quiz['title']}'{integrity_note}",
        link="/",
        category="quiz",
    )

    return {
        "attempt_id": str(result.inserted_id),
        **record,
        "question_count": len(questions),
        "percentage": round((score / max(quiz["total_marks"], 1)) * 100, 1),
        "student_name": current_student.get("name"),
    }


# ── Results ─────────────────────────────────────────────────────────────────
@router.get("/{quiz_id}/my-attempt")
async def my_attempt(
    quiz_id: str,
    current_student: dict = Depends(get_current_student),
    db=Depends(get_db),
):
    """Student views their own attempt with question-by-question feedback."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id)})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempt = await db["quiz_attempts"].find_one({
        "quiz_id": quiz_id, "student_id": current_student["id"]
    })
    if not attempt:
        raise HTTPException(status_code=404, detail="No attempt found")

    show_correct = quiz.get("show_correct_after", True)
    questions = quiz["questions"]
    detailed = []
    for i, q in enumerate(questions):
        qtype = q.get("type", "mcq")
        unanswered = "" if qtype == "short_answer" else -1
        student_ans = attempt["answers"][i] if i < len(attempt["answers"]) else unanswered
        correct = is_correct(q, student_ans)
        if qtype == "short_answer":
            correct_answer = (q.get("accepted_answers") or [None])[0] if show_correct else None
        else:
            correct_answer = q["correct_index"] if show_correct else None
        detailed.append({
            "type": qtype,
            "question_text": q["question_text"],
            "options": q.get("options") or [],
            "student_answer": student_ans,
            "correct_answer": correct_answer,
            "accepted_answers": (q.get("accepted_answers") or []) if (show_correct and qtype == "short_answer") else None,
            "is_correct": correct,
            "marks": q.get("marks", 1),
            "marks_earned": q.get("marks", 1) if correct else 0,
            "explanation": q.get("explanation") if show_correct else None,
        })

    return {
        "attempt_id": str(attempt["_id"]),
        "quiz_title": quiz["title"],
        "score": attempt["score"],
        "total_marks": attempt["total_marks"],
        "correct_count": attempt["correct_count"],
        "question_count": len(questions),
        "percentage": round((attempt["score"] / max(attempt["total_marks"], 1)) * 100, 1),
        "time_taken_seconds": attempt["time_taken_seconds"],
        "submitted_at": attempt["submitted_at"].isoformat(),
        "auto_submitted": attempt.get("auto_submitted", False),
        "show_correct_after": show_correct,
        "questions": detailed,
    }


@router.get("/{quiz_id}/attempts", response_model=List[QuizAttemptOut])
async def list_attempts(
    quiz_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher: list all student attempts for a quiz."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id), "teacher_id": current_teacher["id"]})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    cursor = db["quiz_attempts"].find({"quiz_id": quiz_id}).sort("submitted_at", -1)
    attempts = await cursor.to_list(length=500)

    # Fetch student names
    student_ids = [a["student_id"] for a in attempts]
    valid_oids = [ObjectId(s) for s in student_ids if ObjectId.is_valid(s)]
    users = {}
    if valid_oids:
        cur = db["users"].find({"_id": {"$in": valid_oids}})
        for u in await cur.to_list(length=500):
            users[str(u["_id"])] = u.get("name", "Unknown")

    out = []
    for a in attempts:
        out.append({
            "attempt_id": str(a["_id"]),
            **a,
            "student_name": users.get(a["student_id"], "Unknown"),
            "question_count": len(quiz["questions"]),
            "percentage": round((a["score"] / max(a["total_marks"], 1)) * 100, 1),
        })
    return out


@router.post("/{quiz_id}/attempts/{student_id}/reset")
async def reset_attempt(
    quiz_id: str,
    student_id: str,
    body: AttemptResetBody,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """
    Teacher override: remove a student's attempt (and any open session) so they can take the
    quiz again. Needs a reason; the override is written to the audit log.
    """
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id), "teacher_id": current_teacher["id"]})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")
    attempt = await db["quiz_attempts"].find_one({"quiz_id": quiz_id, "student_id": student_id})
    session = await db["quiz_sessions"].find_one({"quiz_id": quiz_id, "student_id": student_id})
    if not attempt and not session:
        raise HTTPException(status_code=404, detail="This student has no attempt to reset")
    try:
        await record_audit(
            db, current_teacher, "quiz_attempt_reset", "quiz", quiz_id, body.reason,
            details={
                "quiz_title": quiz.get("title"), "student_id": student_id,
                "previous_score": attempt.get("score") if attempt else None,
                "previous_total": attempt.get("total_marks") if attempt else None,
                "submitted_at": attempt.get("submitted_at").isoformat() if attempt and attempt.get("submitted_at") else None,
            },
        )
    except AuditError as e:
        raise HTTPException(status_code=400, detail=str(e))
    await db["quiz_attempts"].delete_many({"quiz_id": quiz_id, "student_id": student_id})
    await db["quiz_sessions"].delete_many({"quiz_id": quiz_id, "student_id": student_id})
    await notify_user(
        db,
        user_id=student_id,
        title="Quiz reopened for you",
        body=f"Your teacher allowed a new attempt at '{quiz.get('title')}' ({body.reason.strip()})",
        link="/",
        category="quiz",
    )
    return {"reset": True, "quiz_id": quiz_id, "student_id": student_id}


@router.get("/{quiz_id}/stats")
async def quiz_stats(
    quiz_id: str,
    current_teacher: dict = Depends(get_current_teacher),
    db=Depends(get_db),
):
    """Teacher: aggregate stats for a quiz (avg score, hardest question, etc.)."""
    if not ObjectId.is_valid(quiz_id):
        raise HTTPException(status_code=400, detail="Invalid quiz_id")
    quiz = await db["quizzes"].find_one({"_id": ObjectId(quiz_id), "teacher_id": current_teacher["id"]})
    if not quiz:
        raise HTTPException(status_code=404, detail="Quiz not found")

    attempts = await db["quiz_attempts"].find({"quiz_id": quiz_id}).to_list(length=1000)

    if not attempts:
        return {
            "quiz_id": quiz_id,
            "title": quiz["title"],
            "attempt_count": 0,
            "average_score": None,
            "average_percentage": None,
            "highest_score": None,
            "lowest_score": None,
            "average_time_seconds": None,
            "auto_submit_count": 0,
            "question_stats": [],
        }

    scores = [a["score"] for a in attempts]
    percentages = [(a["score"] / max(a["total_marks"], 1)) * 100 for a in attempts]
    times = [a["time_taken_seconds"] for a in attempts]

    # Per-question correctness
    questions = quiz["questions"]
    question_stats = []
    for i, q in enumerate(questions):
        correct = sum(1 for a in attempts if i < len(a["answers"]) and is_correct(q, a["answers"][i]))
        question_stats.append({
            "question_index": i,
            "question_text": q["question_text"][:80],
            "correct_count": correct,
            "incorrect_count": len(attempts) - correct,
            "correct_rate": round((correct / len(attempts)) * 100, 1),
        })

    return {
        "quiz_id": quiz_id,
        "title": quiz["title"],
        "attempt_count": len(attempts),
        "average_score": round(sum(scores) / len(scores), 1),
        "average_percentage": round(sum(percentages) / len(percentages), 1),
        "highest_score": max(scores),
        "lowest_score": min(scores),
        "average_time_seconds": round(sum(times) / len(times)),
        "auto_submit_count": sum(1 for a in attempts if a.get("auto_submitted")),
        "question_stats": question_stats,
    }
