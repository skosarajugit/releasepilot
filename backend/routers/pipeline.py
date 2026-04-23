# backend/routers/pipeline.py
#
# Endpoints for CI/CD pipeline stage data.
#
# GET  /pipeline/release/{id}         → all stages for a release
# POST /pipeline/release/{id}/advance → simulate advancing the pipeline (for demo)

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime

from backend.database import get_db
from backend.models import PipelineStage, Release, PipelineStageStatus
from backend.schemas import PipelineStageRead
from typing import List

router = APIRouter()


@router.get("/release/{release_id}", response_model=List[PipelineStageRead])
def get_pipeline(release_id: int, db: Session = Depends(get_db)):
    """
    Get all pipeline stages for a release, ordered by stage_order.
    Returns the full pipeline so the dashboard can render the visual.
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.release_id == release_id)
        .order_by(PipelineStage.stage_order)
        .all()
    )
    return stages


@router.get("/release/{release_id}/summary")
def get_pipeline_summary(release_id: int, db: Session = Depends(get_db)):
    """
    Get a summary of pipeline health for a release.
    Returns counts by status and the currently running stage.
    """
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.release_id == release_id)
        .all()
    )
    if not stages:
        raise HTTPException(status_code=404, detail=f"No pipeline found for release {release_id}")

    # Find which stage is currently running
    running = next((s for s in stages if s.status == PipelineStageStatus.RUNNING), None)

    return {
        "release_id": release_id,
        "total_stages": len(stages),
        "completed": sum(1 for s in stages if s.status == PipelineStageStatus.SUCCESS),
        "failed": sum(1 for s in stages if s.status == PipelineStageStatus.FAILED),
        "pending": sum(1 for s in stages if s.status == PipelineStageStatus.PENDING),
        "current_stage": running.stage_name if running else None,
        "total_duration_seconds": sum(s.duration_seconds or 0 for s in stages),
    }


@router.post("/release/{release_id}/advance/")
def advance_pipeline(release_id: int, db: Session = Depends(get_db)):
    """
    Demo endpoint — advances the pipeline to the next stage.
    In production this would be triggered by Jenkins/GitHub Actions webhooks.
    Useful for live demos to show the pipeline moving.
    """
    stages = (
        db.query(PipelineStage)
        .filter(PipelineStage.release_id == release_id)
        .order_by(PipelineStage.stage_order)
        .all()
    )
    if not stages:
        raise HTTPException(status_code=404, detail="No pipeline stages found")

    # Find the currently running stage and mark it complete
    running = next((s for s in stages if s.status == PipelineStageStatus.RUNNING), None)
    if running:
        running.status = PipelineStageStatus.SUCCESS
        running.finished_at = datetime.utcnow()
        running.duration_seconds = int((running.finished_at - (running.started_at or running.finished_at)).total_seconds()) or 30

    # Start the next pending stage
    pending = next((s for s in stages if s.status == PipelineStageStatus.PENDING), None)
    if pending:
        pending.status = PipelineStageStatus.RUNNING
        pending.started_at = datetime.utcnow()

    db.commit()
    return {"message": "Pipeline advanced", "now_running": pending.stage_name if pending else "Complete"}
