"""
Quiz Router — Teacher creates MCQ quizzes (manually or via AI),
students take them with a timer, both see results.
"""
import io
import random
from datetime import datetime, timedelta
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Body, File, UploadFile, Form
from pydantic import BaseModel
from bson import ObjectId

from core.timeutil import parse_deadline
from database import get_db
from models.school import QuizOut, QuizAttemptOut
from routers.deps import get_current_teacher, get_current_student, get_current_user
from services.quiz_generator import generate_quiz_questions
from services.notifications import notify_user

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


def _extract_pdf_text(pdf_bytes: bytes) -> str:
    """
    Extract embedded text from a PDF using PyMuPDF (fitz).
    This is fast and works for typed PDFs; scanned/handwritten PDFs will return
    little or no text — the caller will surface a helpful error in that case.
    """
    try:
        import fitz  # PyMuPDF
    except ImportError as e:
        raise HTTPException(
            status_code=500,
            detail="PDF extraction requires PyMuPDF. Install with `pip install pymupdf`.",
        ) from e

    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Could not open PDF: {e}")

    chunks = []
    for page in doc:
        try:
            chunks.append(page.get_text("text"))
        except Exception:
            continue
    doc.close()
    return "\n".join(chunks).strip()


# ── Request bodies ──────────────────────────────────────────────────────────
class QuizQuestionInput(BaseModel):
    question_text: str
    options: List[str]
    correct_index: int
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


class QuizSubmitBody(BaseModel):
    answers: List[int]
    started_at: str  # ISO datetime when student started
    auto_submitted: bool = False
    # Integrity / proctoring metrics
    tab_switches: int = 0
    time_away_seconds: int = 0
    copy_attempts: int = 0
    paste_attempts: int = 0


# ── Helpers ─────────────────────────────────────────────────────────────────
def _validate_questions(questions: List[QuizQuestionInput]) -> int:
    """Validate questions and return total_marks."""
    if not questions:
        raise HTTPException(status_code=400, detail="At least one question required")
    total = 0
    for i, q in enumerate(questions):
        if len(q.options) != 4:
            raise HTTPException(status_code=400, detail=f"Question {i+1}: must have exactly 4 options")
        if q.correct_index < 0 or q.correct_index > 3:
            raise HTTPException(status_code=400, detail=f"Question {i+1}: correct_index must be 0-3")
        if not q.question_text.strip():
            raise HTTPException(status_code=400, detail=f"Question {i+1}: text cannot be empty")
        if q.marks < 1:
            raise HTTPException(status_code=400, detail=f"Question {i+1}: marks must be >= 1")
        total += q.marks
    return total


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
    """Teacher uses AI to generate MCQ questions on a topic. Returns draft questions to review."""
    if not body.topic.strip():
        raise HTTPException(status_code=400, detail="Topic is required")
    questions = await generate_quiz_questions(
        topic=body.topic,
        num_questions=body.num_questions,
        difficulty=body.difficulty,
        source_text=body.source_text,
    )
    if not questions:
        raise HTTPException(status_code=500, detail="AI did not return any valid questions. Try again or refine the topic.")
    return {"questions": questions, "count": len(questions)}


@router.post("/generate-from-pdf")
async def generate_quiz_from_pdf(
    file: UploadFile = File(...),
    topic: Optional[str] = Form(None),
    num_questions: int = Form(5),
    difficulty: str = Form("medium"),
    current_teacher: dict = Depends(get_current_teacher),
):
    """
    Teacher uploads a PDF — server extracts its text and generates MCQ
    questions grounded in that content.
    """
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")

    pdf_bytes = await file.read()
    if not pdf_bytes:
        raise HTTPException(status_code=400, detail="Uploaded PDF is empty.")
    if len(pdf_bytes) > 15 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="PDF too large (limit: 15 MB).")

    source_text = _extract_pdf_text(pdf_bytes)
    if len(source_text) < 200:
        raise HTTPException(
            status_code=400,
            detail=(
                "Could not extract enough text from the PDF. "
                "Make sure the PDF contains selectable text (scanned/handwritten "
                "PDFs aren't supported by this fast path)."
            ),
        )

    derived_topic = (topic or "").strip() or (file.filename.rsplit(".", 1)[0])

    questions = await generate_quiz_questions(
        topic=derived_topic,
        num_questions=num_questions,
        difficulty=difficulty,
        source_text=source_text,
    )
    if not questions:
        raise HTTPException(status_code=500, detail="AI did not return any valid questions. Try again.")
    return {
        "questions": questions,
        "count": len(questions),
        "topic": derived_topic,
        "source_chars": len(source_text),
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
        "questions": [q.model_dump() for q in body.questions],
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
        updates["total_marks"] = _validate_questions(body.questions)
        updates["questions"] = [q.model_dump() for q in body.questions]
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

    # Build student-safe view with optional shuffling
    questions = list(quiz["questions"])
    # Track original indices so we can grade correctly after shuffle
    indexed = [{"_orig_idx": i, **q} for i, q in enumerate(questions)]

    if quiz.get("shuffle_questions"):
        random.shuffle(indexed)

    safe_questions = []
    for q in indexed:
        opts = list(q["options"])
        # Track which option is which after shuffle
        option_pairs = list(enumerate(opts))
        if quiz.get("shuffle_options"):
            random.shuffle(option_pairs)
        # Build mapping: original_option_idx -> shuffled_position
        shuffled_options = [pair[1] for pair in option_pairs]
        # We send: position-mapping so we can decode answers later
        # But to keep it stateless, we just send shuffled options & track on submit
        safe_questions.append({
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
        "started_at": datetime.utcnow().isoformat(),
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

    questions = quiz["questions"]
    if len(body.answers) != len(questions):
        raise HTTPException(
            status_code=400,
            detail=f"Expected {len(questions)} answers, got {len(body.answers)}",
        )

    # Grade
    score = 0
    correct_count = 0
    for i, q in enumerate(questions):
        ans = body.answers[i]
        if ans == q["correct_index"]:
            score += q.get("marks", 1)
            correct_count += 1

    try:
        started_at = datetime.fromisoformat(body.started_at.replace("Z", "+00:00"))
        if started_at.tzinfo:
            started_at = started_at.replace(tzinfo=None)
    except (ValueError, AttributeError):
        started_at = datetime.utcnow()

    submitted_at = datetime.utcnow()
    time_taken = max(0, int((submitted_at - started_at).total_seconds()))

    record = {
        "quiz_id": quiz_id,
        "student_id": current_student["id"],
        "answers": body.answers,
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
        student_ans = attempt["answers"][i] if i < len(attempt["answers"]) else -1
        is_correct = student_ans == q["correct_index"]
        detailed.append({
            "question_text": q["question_text"],
            "options": q["options"],
            "student_answer": student_ans,
            "correct_answer": q["correct_index"] if show_correct else None,
            "is_correct": is_correct,
            "marks": q.get("marks", 1),
            "marks_earned": q.get("marks", 1) if is_correct else 0,
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
        correct = sum(1 for a in attempts if i < len(a["answers"]) and a["answers"][i] == q["correct_index"])
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
