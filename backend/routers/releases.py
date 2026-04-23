# backend/routers/releases.py
#
# All API endpoints related to releases.
#
# REST conventions used here:
#   GET    /releases          → list all releases
#   GET    /releases/{id}     → get one release (with commits, blockers, pipeline)
#   POST   /releases          → create a new release
#   PATCH  /releases/{id}     → update a release (partial update)
#   DELETE /releases/{id}     → delete a release
#   GET    /releases/{id}/summary → AI-generated summary of a release

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import Release, ReleaseStatus
from backend.schemas import ReleaseCreate, ReleaseRead, ReleaseReadFull, ReleaseUpdate

# APIRouter is like a mini FastAPI app — it holds a group of related routes.
# We register it in main.py with a prefix so all routes here start with /releases
router = APIRouter()


@router.get("/", response_model=List[ReleaseRead])
def get_releases(
    status: str = None,         # Optional filter: ?status=in_progress
    db: Session = Depends(get_db)
):
    """
    Get all releases, optionally filtered by status.

    Examples:
      GET /releases                        → all releases
      GET /releases?status=in_progress     → only in-progress releases
    """
    query = db.query(Release)

    # Apply filter if status param was provided
    if status:
        try:
            status_enum = ReleaseStatus(status)
            query = query.filter(Release.status == status_enum)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid status '{status}'. Valid values: {[s.value for s in ReleaseStatus]}"
            )

    # Order by most recently updated first
    releases = query.order_by(Release.updated_at.desc()).all()
    return releases


@router.get("/{release_id}/", response_model=ReleaseReadFull)
def get_release(release_id: int, db: Session = Depends(get_db)):
    """
    Get a single release by ID, including all its commits, blockers,
    and pipeline stages.

    ReleaseReadFull includes nested data — SQLAlchemy loads related
    records automatically via the relationships defined in models.py
    """
    release = db.query(Release).filter(Release.id == release_id).first()

    # If no release found, return 404 (not 200 with empty data)
    if not release:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Release with id {release_id} not found"
        )
    return release


@router.post("/", response_model=ReleaseRead, status_code=status.HTTP_201_CREATED)
def create_release(release_in: ReleaseCreate, db: Session = Depends(get_db)):
    """
    Create a new release.

    Request body example:
    {
        "name": "POS-Core",
        "version": "v4.8.0",
        "owner": "J. Alvarez",
        "description": "New payment processing features",
        "target_date": "2024-05-15T00:00:00"
    }

    release_in is automatically validated by Pydantic before this function runs.
    If any required field is missing, FastAPI returns a 422 error automatically.
    """
    # Convert Pydantic schema to SQLAlchemy model
    # model_dump() converts the Pydantic object to a plain dictionary
    release = Release(**release_in.model_dump())
    db.add(release)       # Stage the new record
    db.commit()           # Write to database
    db.refresh(release)   # Reload from DB to get auto-generated fields (id, created_at)
    return release


@router.patch("/{release_id}/", response_model=ReleaseRead)
def update_release(
    release_id: int,
    release_in: ReleaseUpdate,
    db: Session = Depends(get_db)
):
    """
    Partially update a release (PATCH = only update fields you send).

    Example — just update the status:
    PATCH /releases/1
    { "status": "deployed" }

    This won't touch any other fields.
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    # model_dump(exclude_unset=True) only returns fields the user actually sent
    # So PATCH {"status": "deployed"} won't accidentally null out other fields
    update_data = release_in.model_dump(exclude_unset=True)

    for field, value in update_data.items():
        setattr(release, field, value)   # e.g. release.status = "deployed"

    db.commit()
    db.refresh(release)
    return release


@router.delete("/{release_id}/", status_code=status.HTTP_204_NO_CONTENT)
def delete_release(release_id: int, db: Session = Depends(get_db)):
    """
    Delete a release and all its related data (cascade delete).
    Returns 204 No Content on success (standard REST convention).
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    db.delete(release)
    db.commit()
    # 204 responses have no body — just return None


@router.get("/{release_id}/commits/")
def get_release_commits(release_id: int, db: Session = Depends(get_db)):
    """
    Get all commits for a release.
    Used by the AI service to generate release notes.
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    return {
        "release": f"{release.name} {release.version}",
        "commit_count": len(release.commits),
        "commits": [
            {
                "sha": c.sha[:7],
                "type": c.commit_type,
                "message": c.message,
                "author": c.author,
                "jira_ticket": c.jira_ticket,
                "committed_at": c.committed_at,
            }
            for c in sorted(release.commits, key=lambda c: c.committed_at or 0, reverse=True)
        ]
    }
