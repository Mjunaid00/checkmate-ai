from pydantic import BaseModel, Field
from typing import Optional, Literal
from datetime import datetime


class ExamCreate(BaseModel):
    """Metadata submitted alongside the file upload"""
    exam_title:  str = Field(..., min_length=2, max_length=200)
    total_marks: int = Field(..., ge=1, le=1000)


class ExamInDB(BaseModel):
    """Full exam document stored in MongoDB"""
    exam_title:    str
    total_marks:   int
    teacher_id:    str          # ObjectId → str of the uploader
    file_path:     str          # relative path inside /uploads/
    original_name: str          # original filename from the upload
    file_type:     str          # "application/pdf" | "image/jpeg" | …
    file_size:     int          # bytes
    status:        Literal["uploaded", "processing", "graded"] = "uploaded"
    created_at:    datetime = Field(default_factory=datetime.utcnow)


class ExamOut(BaseModel):
    """Public exam response payload"""
    exam_id:       str
    exam_title:    str
    total_marks:   int
    teacher_id:    str
    original_name: str
    status:        str
    score:         Optional[int] = None
    feedback:      Optional[str] = None
    created_at:    datetime

