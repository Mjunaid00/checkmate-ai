from pydantic import BaseModel, EmailStr, Field
from typing import Optional, Literal
from datetime import datetime


# ── User ─────────────────────────────────────────────────────────────────────

class UserCreate(BaseModel):
    """Body schema for POST /auth/register"""
    name:     str   = Field(..., min_length=3, max_length=80)
    email:    EmailStr
    password: str   = Field(..., min_length=6)
    # Admin accounts are NOT self-serve via public register — they must be
    # bootstrapped (env var) or created by another admin. Allowed here so
    # admin-only endpoints can reuse the same model.
    role:     Literal["teacher", "student", "admin"] = "student"


class UserLogin(BaseModel):
    """Body schema for POST /auth/login"""
    email:    EmailStr
    password: str


class UserInDB(BaseModel):
    """Schema stored in MongoDB (password already hashed)"""
    name:            str
    email:           str
    hashed_password: str
    role:            str
    created_at:      datetime = Field(default_factory=datetime.utcnow)
    is_active:       bool     = True
    bio:             Optional[str] = None
    phone:           Optional[str] = None
    institution:     Optional[str] = None


class UserOut(BaseModel):
    """Public user payload — never exposes the password"""
    id:         str
    name:       str
    email:      str
    role:       str
    created_at: datetime
    bio:             Optional[str] = None
    phone:           Optional[str] = None
    institution:     Optional[str] = None


class TokenResponse(BaseModel):
    """Returned after successful login / register"""
    access_token: str
    token_type:   str  = "bearer"
    role:         str
    name:         str


# ── Profile / Settings ──────────────────────────────────────────────────────

class ProfileUpdate(BaseModel):
    """Body schema for PATCH /auth/profile"""
    name:        Optional[str] = Field(None, min_length=2, max_length=80)
    bio:         Optional[str] = Field(None, max_length=300)
    phone:       Optional[str] = Field(None, max_length=20)
    institution: Optional[str] = Field(None, max_length=120)


class PasswordChange(BaseModel):
    """Body schema for POST /auth/change-password"""
    current_password: str = Field(..., min_length=1)
    new_password:     str = Field(..., min_length=6)
