from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Tuple

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter(prefix="/notes", tags=["Notes"])


# ── Helpers ───────────────────────────────────────────────────────────────────


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _get_note_or_404(note_id: str, db: Session) -> models.Note:
    note = db.query(models.Note).filter(models.Note.id == note_id).first()
    if not note:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Note not found")
    return note


def _assert_access(
    note: models.Note, current_user: models.User, db: Session
) -> bool:
    """Return True if owner, False if shared. Raise 403 if neither."""
    if note.owner_id == current_user.id:
        return True  # is owner

    shared = (
        db.query(models.NoteShare)
        .filter(
            models.NoteShare.note_id == note.id,
            models.NoteShare.shared_with_user_id == current_user.id,
        )
        .first()
    )
    if shared:
        return False  # has read/write access via share

    raise HTTPException(
        status_code=status.HTTP_403_FORBIDDEN,
        detail="You do not have access to this note",
    )


def _save_version(note: models.Note, db: Session) -> None:
    """Snapshot current note content as a new version record."""
    count = (
        db.query(models.NoteVersion)
        .filter(models.NoteVersion.note_id == note.id)
        .count()
    )
    version = models.NoteVersion(
        note_id=note.id,
        title=note.title,
        content=note.content,
        version_number=count + 1,
    )
    db.add(version)


# ── Core CRUD ─────────────────────────────────────────────────────────────────


@router.get(
    "",
    response_model=List[schemas.NoteResponse],
    summary="Get all accessible notes (owned + shared)",
)
def get_notes(
    page: int = Query(1, ge=1, description="Page number (1-indexed)"),
    per_page: int = Query(100, ge=1, le=200, description="Items per page"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns all notes the authenticated user can access — both notes they own
    and notes shared with them. Supports optional pagination via `page` and
    `per_page` query params. Pinned notes always appear first.
    """
    owned_ids = db.query(models.Note.id).filter(
        models.Note.owner_id == current_user.id
    )
    shared_ids = db.query(models.NoteShare.note_id).filter(
        models.NoteShare.shared_with_user_id == current_user.id
    )

    query = (
        db.query(models.Note)
        .filter(or_(models.Note.id.in_(owned_ids), models.Note.id.in_(shared_ids)))
        .order_by(models.Note.is_pinned.desc(), models.Note.updated_at.desc())
    )

    notes = query.offset((page - 1) * per_page).limit(per_page).all()
    return notes


@router.get(
    "/{note_id}",
    response_model=schemas.NoteResponse,
    summary="Get a specific note by ID",
)
def get_note(
    note_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note_or_404(note_id, db)
    _assert_access(note, current_user, db)
    return note


@router.post(
    "",
    response_model=schemas.NoteResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new note",
)
def create_note(
    body: schemas.NoteCreate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = models.Note(
        title=body.title,
        content=body.content,
        owner_id=current_user.id,
    )
    db.add(note)
    db.commit()
    db.refresh(note)
    return note


@router.put(
    "/{note_id}",
    response_model=schemas.NoteResponse,
    summary="Update an existing note",
)
def update_note(
    note_id: str,
    body: schemas.NoteUpdate,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note_or_404(note_id, db)
    is_owner = _assert_access(note, current_user, db)

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can update it",
        )

    # ── Custom feature: snapshot current state before overwriting ──
    _save_version(note, db)

    note.title = body.title
    note.content = body.content
    note.updated_at = utcnow()

    db.commit()
    db.refresh(note)
    return note


@router.delete(
    "/{note_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a note",
)
def delete_note(
    note_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note_or_404(note_id, db)
    is_owner = _assert_access(note, current_user, db)

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can delete it",
        )

    db.delete(note)
    db.commit()


@router.post(
    "/{note_id}/share",
    summary="Share a note with another user",
)
def share_note(
    note_id: str,
    body: schemas.ShareNote,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note_or_404(note_id, db)
    is_owner = _assert_access(note, current_user, db)

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can share it",
        )

    target = (
        db.query(models.User).filter(models.User.email == body.share_with_email).first()
    )
    if not target:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No user found with that email address",
        )
    if target.id == current_user.id:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="You cannot share a note with yourself",
        )

    already_shared = (
        db.query(models.NoteShare)
        .filter(
            models.NoteShare.note_id == note_id,
            models.NoteShare.shared_with_user_id == target.id,
        )
        .first()
    )
    if already_shared:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="This note is already shared with that user",
        )

    share = models.NoteShare(note_id=note_id, shared_with_user_id=target.id)
    db.add(share)
    db.commit()

    return {"message": f"Note shared successfully with {body.share_with_email}"}


# ── Custom Feature: Version History ──────────────────────────────────────────
# Every PUT /notes/{id} automatically snapshots the previous content.
# Users can browse versions and restore any of them.


@router.get(
    "/{note_id}/versions",
    response_model=List[schemas.NoteVersionResponse],
    summary="[Custom] List all saved versions of a note",
)
def list_versions(
    note_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Returns the full version history of a note, newest first.
    A new version is saved automatically every time the note is updated via PUT.
    Both the owner and users the note is shared with can view the history.
    """
    note = _get_note_or_404(note_id, db)
    _assert_access(note, current_user, db)

    versions = (
        db.query(models.NoteVersion)
        .filter(models.NoteVersion.note_id == note_id)
        .order_by(models.NoteVersion.version_number.desc())
        .all()
    )
    return versions


@router.post(
    "/{note_id}/versions/{version_id}/restore",
    response_model=schemas.NoteResponse,
    summary="[Custom] Restore a note to a previous version",
)
def restore_version(
    note_id: str,
    version_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Restores the note to the given saved version.
    The current state is snapshotted first so nothing is ever lost.
    Only the note owner can restore versions.
    """
    note = _get_note_or_404(note_id, db)
    is_owner = _assert_access(note, current_user, db)

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can restore versions",
        )

    version = (
        db.query(models.NoteVersion)
        .filter(
            models.NoteVersion.id == version_id,
            models.NoteVersion.note_id == note_id,
        )
        .first()
    )
    if not version:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Version not found",
        )

    # Snapshot current state before restoring
    _save_version(note, db)

    note.title = version.title
    note.content = version.content
    note.updated_at = utcnow()

    db.commit()
    db.refresh(note)
    return note


# ── Bonus: Note Pinning ───────────────────────────────────────────────────────


@router.patch(
    "/{note_id}/pin",
    response_model=schemas.NoteResponse,
    summary="[Bonus] Toggle pin status — pinned notes appear first",
)
def toggle_pin(
    note_id: str,
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    note = _get_note_or_404(note_id, db)
    is_owner = _assert_access(note, current_user, db)

    if not is_owner:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the note owner can pin/unpin it",
        )

    note.is_pinned = not note.is_pinned
    db.commit()
    db.refresh(note)
    return note
