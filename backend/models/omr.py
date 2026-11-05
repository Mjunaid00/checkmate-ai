"""
OMR (Optical Mark Recognition) Models
Supports both MCQ and True/False structured answer sheets.
"""
from pydantic import BaseModel, Field
from typing import List, Optional, Literal
from datetime import datetime


# ── OMR Template (Teacher-defined answer key) ────────────────────────────────
class OMRTemplateInDB(BaseModel):
    class_id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    sheet_type: Literal["mcq", "true_false"] = "mcq"
    num_questions: int
    options_per_question: int = 4  # 4 for MCQ, 2 for T/F
    answer_key: List[int]  # correct option index per question (0-based)
    marks_per_question: int = 1
    total_marks: int  # num_questions * marks_per_question
    negative_marking: float = 0.0  # marks deducted per wrong answer (0 = none)
    deadline: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OMRTemplateOut(BaseModel):
    template_id: str
    class_id: str
    teacher_id: str
    title: str
    description: Optional[str] = None
    sheet_type: str
    num_questions: int
    options_per_question: int
    # Note: answer_key is hidden from students
    answer_key: Optional[List[int]] = None
    marks_per_question: int
    total_marks: int
    negative_marking: float
    deadline: Optional[datetime] = None
    submission_count: Optional[int] = None
    has_submitted: Optional[bool] = None
    created_at: datetime


# ── OMR Submission (Filled sheet) ───────────────────────────────────────────
class OMRSubmissionInDB(BaseModel):
    template_id: str
    class_id: str
    submitter_id: Optional[str] = None  # student id; None for teacher batch entries
    submitter_role: Literal["student", "teacher_batch"] = "student"
    candidate_label: Optional[str] = None  # for teacher batch: original filename or roll #
    student_id_number: Optional[str] = None  # academic ID
    sheet_image_path: str
    original_name: str
    detected_answers: Optional[List[int]] = None  # index per question, -1 = blank/unclear
    correct_count: Optional[int] = None
    incorrect_count: Optional[int] = None
    blank_count: Optional[int] = None
    score: Optional[float] = None
    total_marks: int
    percentage: Optional[float] = None
    status: Literal["pending", "processing", "graded", "failed"] = "pending"
    error_message: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


class OMRSubmissionOut(BaseModel):
    submission_id: str
    template_id: str
    template_title: Optional[str] = None
    class_id: str
    submitter_id: Optional[str] = None
    submitter_role: str
    submitter_name: Optional[str] = None
    candidate_label: Optional[str] = None
    student_id_number: Optional[str] = None
    original_name: str
    detected_answers: Optional[List[int]] = None
    correct_count: Optional[int] = None
    incorrect_count: Optional[int] = None
    blank_count: Optional[int] = None
    score: Optional[float] = None
    total_marks: int
    percentage: Optional[float] = None
    status: str
    error_message: Optional[str] = None
    created_at: datetime
