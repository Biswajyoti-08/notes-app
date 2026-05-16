from typing import List

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import or_
from sqlalchemy.orm import Session

import auth
import models
import schemas
from database import get_db

router = APIRouter(tags=["Search"])


@router.get(
    "/search",
    response_model=List[schemas.NoteResponse],
    summary="Full-text search across all accessible notes",
)
def search_notes(
    q: str = Query(..., min_length=1, description="Keyword to search for"),
    current_user: models.User = Depends(auth.get_current_user),
    db: Session = Depends(get_db),
):
    """
    Searches title and content of all notes accessible to the authenticated user
    (owned + shared). Returns matches sorted by last updated, pinned notes first.
    """
    term = q.strip()
    if not term:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Search query cannot be empty",
        )

    like = f"%{term}%"

    owned_ids = db.query(models.Note.id).filter(
        models.Note.owner_id == current_user.id
    )
    shared_ids = db.query(models.NoteShare.note_id).filter(
        models.NoteShare.shared_with_user_id == current_user.id
    )

    results = (
        db.query(models.Note)
        .filter(
            or_(models.Note.id.in_(owned_ids), models.Note.id.in_(shared_ids)),
            or_(
                models.Note.title.ilike(like),
                models.Note.content.ilike(like),
            ),
        )
        .order_by(models.Note.is_pinned.desc(), models.Note.updated_at.desc())
        .all()
    )

    return results
