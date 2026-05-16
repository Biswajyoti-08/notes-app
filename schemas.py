from __future__ import annotations

from datetime import datetime
from typing import List

from pydantic import BaseModel, EmailStr, field_validator


# ── Auth ──────────────────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    email: EmailStr
    password: str

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        if len(v) < 8:
            raise ValueError("Password must be at least 8 characters long")
        return v


class UserLogin(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


# ── Notes ─────────────────────────────────────────────────────────────────────

class NoteCreate(BaseModel):
    title: str
    content: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 500:
            raise ValueError("Title cannot exceed 500 characters")
        return v


class NoteUpdate(BaseModel):
    title: str
    content: str

    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Title cannot be empty")
        if len(v) > 500:
            raise ValueError("Title cannot exceed 500 characters")
        return v


class NoteResponse(BaseModel):
    id: str
    title: str
    content: str
    is_pinned: bool
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class NoteVersionResponse(BaseModel):
    id: str
    note_id: str
    title: str
    content: str
    version_number: int
    created_at: datetime

    model_config = {"from_attributes": True}


class PaginatedNotesResponse(BaseModel):
    total: int
    page: int
    per_page: int
    notes: List[NoteResponse]


# ── Share ─────────────────────────────────────────────────────────────────────

class ShareNote(BaseModel):
    share_with_email: EmailStr
