# backend/routers/blockers.py
#
# Endpoints for managing release blockers.
#
# GET    /blockers                   → all open blockers across all releases
# GET    /blockers/release/{id}      → blockers for a specific release
# POST   /blockers/release/{id}      → create a blocker for a release
# PATCH  /blockers/{id}              → update a blocker
# POST   /blockers/{id}/resolve      → mark as resolved
# POST   /blockers/{id}/escalate     → mark as escalated

from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List

from backend.database import get_db
from backend.models import Blocker, Release, BlockerStatus
from backend.schemas import BlockerCreate, BlockerRead, BlockerUpdate

router = APIRouter()


@router.get("/", response_model=List[BlockerRead])
def get_all_blockers(
    status: str = None,      # Filter by status: ?status=open
    severity: str = None,    # Filter by severity: ?severity=high
    db: Session = Depends(get_db)
):
    """
    Get all blockers across all releases.
    Useful for the dashboard risk overview panel.
    """
    query = db.query(Blocker)

    if status:
        try:
            query = query.filter(Blocker.status == BlockerStatus(status))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid status: {status}")

    if severity:
        from backend.models import BlockerSeverity
        try:
            query = query.filter(Blocker.severity == BlockerSeverity(severity))
        except ValueError:
            raise HTTPException(status_code=400, detail=f"Invalid severity: {severity}")

    # Show most severe first, then most recent
    return query.order_by(Blocker.created_at.desc()).all()


@router.get("/release/{release_id}", response_model=List[BlockerRead])
def get_blockers_for_release(release_id: int, db: Session = Depends(get_db)):
    """Get all blockers for a specific release"""
    # Verify the release exists first
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    return db.query(Blocker).filter(Blocker.release_id == release_id).all()


@router.post("/release/{release_id}/", response_model=BlockerRead, status_code=201)
def create_blocker(
    release_id: int,
    blocker_in: BlockerCreate,
    db: Session = Depends(get_db)
):
    """
    Create a new blocker for a release.

    Example request body:
    {
        "title": "DB migration missing rollback plan",
        "description": "The ALTER TABLE statements have no corresponding rollback script",
        "severity": "high",
        "assigned_to": "K. Williams",
        "jira_ticket": "CLOVER-4821"
    }
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    blocker = Blocker(release_id=release_id, **blocker_in.model_dump())
    db.add(blocker)
    db.commit()
    db.refresh(blocker)
    return blocker


@router.patch("/{blocker_id}/", response_model=BlockerRead)
def update_blocker(
    blocker_id: int,
    blocker_in: BlockerUpdate,
    db: Session = Depends(get_db)
):
    """Partially update a blocker (e.g. assign it, add AI suggestion)"""
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail=f"Blocker {blocker_id} not found")

    for field, value in blocker_in.model_dump(exclude_unset=True).items():
        setattr(blocker, field, value)

    db.commit()
    db.refresh(blocker)
    return blocker


@router.post("/{blocker_id}/resolve/", response_model=BlockerRead)
def resolve_blocker(blocker_id: int, db: Session = Depends(get_db)):
    """
    Mark a blocker as resolved.
    This is a dedicated endpoint (not just PATCH) because it also sets resolved_at timestamp.
    """
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail=f"Blocker {blocker_id} not found")

    blocker.status = BlockerStatus.RESOLVED
    blocker.resolved_at = datetime.utcnow()
    db.commit()
    db.refresh(blocker)
    return blocker


@router.post("/{blocker_id}/escalate/", response_model=BlockerRead)
def escalate_blocker(blocker_id: int, db: Session = Depends(get_db)):
    """Mark a blocker as escalated (needs management attention)"""
    blocker = db.query(Blocker).filter(Blocker.id == blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail=f"Blocker {blocker_id} not found")

    blocker.status = BlockerStatus.ESCALATED
    db.commit()
    db.refresh(blocker)
    return blocker
