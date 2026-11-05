from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Union
from datetime import datetime

# ── Class Groups ─────────────────────────────────────────────────────────────
class ClassGroupInDB(BaseModel):
    name: str
    teacher_id: str
    max_students: Optional[int] = None  # None = unlimited
    created_at: datetime = Field(default_factory=datetime.utcnow)

class ClassGroupOut(BaseModel):
    class_id: str
    name: str
    teacher_id: str
    max_students: Optional[int] = None
    enrollment_count: Optional[int] = None  # Current enrolled student count
    assignments_count: Optional[int] = None  # Assignments in this class
    created_at: datetime
    enrolled: Optional[bool] = None  # For students: whether they are enrolled

# ── Enrollment ───────────────────────────────────────────────────────────────
class EnrollmentInDB(BaseModel):
    class_id: str
    student_id: str
    student_id_number: str  # Academic/registration ID provided when enrolling
    enrolled_at: datetime = Field(default_factory=datetime.utcnow)

class EnrollmentOut(BaseModel):
    class_id: str
    student_id: str
    student_id_number: Optional[str] = None
    enrolled_at: datetime

# ── Assignments (Created by Teachers) ────────────────────────────────────────
class AssignmentInDB(BaseModel):
    class_id: str
    teacher_id: str
    title: str
    total_marks: int
    grading_prompt: Optional[str] = None
    deadline: Optional[datetime] = None
    rubric_file_path: str
    original_name: str
    file_type: str
    plagiarism_check: bool = False  # If True, check submissions for similarity
    allowed_formats: Optional[List[str]] = None  # e.g. ["pdf", "png"] (None = all defaults)
    created_at: datetime = Field(default_factory=datetime.utcnow)

class AssignmentOut(BaseModel):
    assignment_id: str
    class_id: str
    teacher_id: str
    title: str
    total_marks: int
    grading_prompt: Optional[str] = None
    deadline: Optional[datetime] = None
    plagiarism_check: bool = False
    allowed_formats: Optional[List[str]] = None
    original_name: str
    created_at: datetime

# ── Explainable Grading Breakdown ────────────────────────────────────────────
class GradingCriterion(BaseModel):
    criterion: str
    marks_awarded: int
    marks_possible: int
    reason: str

class ExplainableFeedback(BaseModel):
    overall_comment: str
    criteria: List[GradingCriterion]
    strengths: List[str]
    improvements: List[str]

# ── Submissions (Uploaded by Students) ───────────────────────────────────────
class SubmissionInDB(BaseModel):
    assignment_id: str
    student_id: str
    answer_file_path: str
    original_name: str
    file_type: str
    status: Literal["uploaded", "processing", "graded", "failed"] = "uploaded"
    score: Optional[int] = None
    feedback: Optional[str] = None
    explainable_feedback: Optional[dict] = None
    # Manual grading (teacher overrides)
    manual_score: Optional[float] = None
    manual_feedback: Optional[str] = None
    manually_graded_at: Optional[datetime] = None
    manually_graded_by: Optional[str] = None
    # Plagiarism / similarity
    similarity_max: Optional[float] = None  # 0.0-1.0, max similarity vs other submissions
    similarity_partner_id: Optional[str] = None  # which submission was most similar
    plagiarism_checked_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

class SubmissionOut(BaseModel):
    submission_id: str
    assignment_id: str
    student_id: str
    original_name: str
    status: str
    score: Optional[int] = None
    total_marks: int
    feedback: Optional[str] = None
    explainable_feedback: Optional[dict] = None
    manual_score: Optional[float] = None
    manual_feedback: Optional[str] = None
    manually_graded_at: Optional[datetime] = None
    similarity_max: Optional[float] = None
    similarity_partner_id: Optional[str] = None
    plagiarism_checked_at: Optional[datetime] = None
    created_at: datetime


# ── Quizzes (MCQ-based) ──────────────────────────────────────────────────────
class QuizQuestion(BaseModel):
    question_text: str
    options: List[str]  # Exactly 4 options
    correct_index: int  # 0-3
    marks: int = 1
    explanation: Optional[str] = None


class QuizInDB(BaseModel):
    class_id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    questions: List[dict]  # List of QuizQuestion as dicts
    total_marks: int
    time_limit_minutes: int = 30
    deadline: Optional[datetime] = None
    shuffle_questions: bool = True
    shuffle_options: bool = True
    show_correct_after: bool = True
    created_at: datetime = Field(default_factory=datetime.utcnow)


class QuizOut(BaseModel):
    quiz_id: str
    class_id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    questions: Optional[List[dict]] = None  # Hidden in student-safe view
    total_marks: int
    question_count: int
    time_limit_minutes: int
    deadline: Optional[datetime] = None
    shuffle_questions: bool = True
    shuffle_options: bool = True
    show_correct_after: bool = True
    created_at: datetime
    has_attempted: Optional[bool] = None  # For students: have they taken it
    attempt_count: Optional[int] = None  # For teachers: total attempts


class QuizAttemptInDB(BaseModel):
    quiz_id: str
    student_id: str
    answers: List[Union[int, str]]
    score: int
    total_marks: int
    correct_count: int
    started_at: datetime
    submitted_at: datetime
    time_taken_seconds: int
    auto_submitted: bool = False
    # Integrity / proctoring metrics captured during the attempt
    tab_switches: int = 0
    time_away_seconds: int = 0
    copy_attempts: int = 0
    paste_attempts: int = 0


class QuizAttemptOut(BaseModel):
    attempt_id: str
    quiz_id: str
    student_id: str
    student_name: Optional[str] = None
    answers: List[Union[int, str]]
    score: int
    total_marks: int
    correct_count: int
    question_count: int
    percentage: float
    started_at: datetime
    submitted_at: datetime
    time_taken_seconds: int
    auto_submitted: bool
    status: Optional[str] = "submitted"
    late_by_seconds: Optional[int] = 0
    tab_switches: Optional[int] = 0
    time_away_seconds: Optional[int] = 0
    copy_attempts: Optional[int] = 0
    paste_attempts: Optional[int] = 0
