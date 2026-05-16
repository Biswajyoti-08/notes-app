import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Text, DateTime, ForeignKey, Integer, Boolean, UniqueConstraint
from sqlalchemy.orm import relationship
from database import Base


def gen_uuid() -> str:
    return str(uuid.uuid4())


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=gen_uuid)
    email = Column(String, unique=True, index=True, nullable=False)
    hashed_password = Column(String, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    owned_notes = relationship(
        "Note", back_populates="owner", cascade="all, delete-orphan"
    )
    shared_notes = relationship(
        "NoteShare", back_populates="shared_with_user", cascade="all, delete-orphan"
    )


class Note(Base):
    __tablename__ = "notes"

    id = Column(String, primary_key=True, default=gen_uuid)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    owner_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    is_pinned = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=utcnow)
    updated_at = Column(DateTime, default=utcnow)

    owner = relationship("User", back_populates="owned_notes")
    shares = relationship("NoteShare", back_populates="note", cascade="all, delete-orphan")
    versions = relationship(
        "NoteVersion",
        back_populates="note",
        cascade="all, delete-orphan",
        order_by="NoteVersion.version_number.desc()",
    )


class NoteShare(Base):
    __tablename__ = "note_shares"
    __table_args__ = (UniqueConstraint("note_id", "shared_with_user_id"),)

    id = Column(String, primary_key=True, default=gen_uuid)
    note_id = Column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    shared_with_user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    shared_at = Column(DateTime, default=utcnow)

    note = relationship("Note", back_populates="shares")
    shared_with_user = relationship("User", back_populates="shared_notes")


class NoteVersion(Base):
    """Custom feature: Automatic version history on every note update."""

    __tablename__ = "note_versions"

    id = Column(String, primary_key=True, default=gen_uuid)
    note_id = Column(String, ForeignKey("notes.id", ondelete="CASCADE"), nullable=False)
    title = Column(String(500), nullable=False)
    content = Column(Text, nullable=False, default="")
    version_number = Column(Integer, nullable=False)
    created_at = Column(DateTime, default=utcnow)

    note = relationship("Note", back_populates="versions")
