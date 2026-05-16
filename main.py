from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from database import Base, engine
from routers import notes, search, users

# Create all tables on startup (idempotent)
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Notes API",
    description=(
        "A multi-user notes service with JWT authentication, note sharing, "
        "full-text search, pagination, version history, and note pinning."
    ),
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Custom 422 handler: flatten pydantic validation errors into readable messages ──
@app.exception_handler(422)
async def validation_exception_handler(request: Request, exc):
    from fastapi.exceptions import RequestValidationError

    errors = exc.errors() if hasattr(exc, "errors") else []
    messages = []
    for e in errors:
        loc = " → ".join(str(l) for l in e.get("loc", []) if l != "body")
        msg = e.get("msg", "Invalid value")
        messages.append(f"{loc}: {msg}" if loc else msg)
    return JSONResponse(
        status_code=422,
        content={"detail": messages or ["Validation error"]},
    )


app.include_router(users.router)
app.include_router(notes.router)
app.include_router(search.router)


@app.get("/about", tags=["Meta"])
def about():
    return {
        "name": "Samanta Biswajyoti Mohapatra",           # ← fill in before submitting
        "email": "mohapatrasamanta25@gmail.com",    # ← fill in before submitting
        "my features": {
            "Note Version History": (
                "Every time a note is updated via PUT /notes/{id}, the previous "
                "title and content are automatically snapshotted into a version "
                "record. Users can list all versions at GET /notes/{id}/versions "
                "and restore any of them at POST /notes/{id}/versions/{version_id}/restore. "
                "Before a restore the current state is also snapshotted, so nothing "
                "is ever permanently lost. Chosen because accidental overwrites are "
                "the #1 data-loss scenario in notes apps; version history is the "
                "safety net users expect from Google Docs and Notion."
            ),
            "Note Pinning": (
                "PATCH /notes/{id}/pin toggles the is_pinned flag. Pinned notes "
                "always appear at the top of GET /notes results, before the "
                "updated_at sort. Chosen because 'starring' or 'pinning' important "
                "items is a core productivity pattern in every major notes app."
            ),
            "Full-text search": (
                "GET /search?q=keyword searches both title and content of all "
                "accessible notes (owned + shared) using a case-insensitive LIKE "
                "query. Results are sorted by pinned first, then last updated."
            ),
            "Pagination": (
                "GET /notes accepts optional ?page and ?per_page query params "
                "(defaults: page=1, per_page=100, max per_page=200). Allows "
                "clients to page through large note collections efficiently."
            ),
        },
    }
