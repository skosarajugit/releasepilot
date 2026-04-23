# backend/routers/ai.py
#
# All AI-powered endpoints.
# These endpoints fetch data from the database, then pass it to
# the AI service (Ollama) to generate intelligent responses.
#
# POST /ai/release-notes    → generate release notes for a release
# POST /ai/triage           → triage a specific blocker
# POST /ai/dora-plan        → generate DORA improvement plan
# POST /ai/cab-brief        → generate CAB meeting brief
# POST /ai/sprint-summary   → generate overall sprint health summary

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import Release, Blocker, DeployEvent
from backend.schemas import (
    AIReleaseNotesRequest, AITriageRequest,
    AIDoraPlanRequest, AICABBriefRequest, AIResponse
)
from backend.services import ai_service
from backend.services.metrics_service import calculate_dora_metrics

router = APIRouter()


@router.post("/release-notes", response_model=AIResponse)
async def generate_release_notes(
    request: AIReleaseNotesRequest,
    db: Session = Depends(get_db)
):
    """
    Generate AI release notes for a release.

    Fetches the release's commits from the database,
    then asks Ollama to write release notes for the chosen audience.

    Request body:
    {
        "release_id": 1,
        "audience": "engineering"   // engineering | product | merchant | cab
    }
    """
    # Fetch the release and its commits
    release = db.query(Release).filter(Release.id == request.release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {request.release_id} not found")

    # Convert commits to simple dicts for the AI service
    commits = [
        {
            "sha": c.sha[:7],
            "type": c.commit_type,
            "message": c.message,
            "author": c.author,
            "jira_ticket": c.jira_ticket,
        }
        for c in release.commits
    ]

    if not commits:
        raise HTTPException(
            status_code=400,
            detail="No commits found for this release. Add commits before generating notes."
        )

    # Call the AI service
    result = await ai_service.generate_release_notes(
        release_name=release.name,
        version=release.version,
        commits=commits,
        audience=request.audience,
    )

    return AIResponse(
        result=result,
        model_used=f"ollama/{ai_service.settings.OLLAMA_MODEL}",
        release_id=release.id,
    )


@router.post("/triage", response_model=AIResponse)
async def triage_blocker(
    request: AITriageRequest,
    db: Session = Depends(get_db)
):
    """
    AI-triage a specific blocker and save the suggestion to the database.

    After calling this, the blocker's ai_suggestion field is populated
    so the dashboard can show it without calling the AI again.

    Request body:
    { "blocker_id": 1 }
    """
    blocker = db.query(Blocker).filter(Blocker.id == request.blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail=f"Blocker {request.blocker_id} not found")

    # Get the release name for context
    release = db.query(Release).filter(Release.id == blocker.release_id).first()
    release_name = f"{release.name} {release.version}" if release else "Unknown Release"

    # Call AI
    result = await ai_service.triage_blocker(
        title=blocker.title,
        description=blocker.description or "",
        severity=blocker.severity.value,
        release_name=release_name,
    )

    # Save the suggestion to the DB so we don't need to call AI again
    blocker.ai_suggestion = result
    db.commit()

    return AIResponse(
        result=result,
        model_used=f"ollama/{ai_service.settings.OLLAMA_MODEL}",
        blocker_id=blocker.id,
    )


@router.post("/dora-plan", response_model=AIResponse)
async def dora_improvement_plan(
    request: AIDoraPlanRequest,
    db: Session = Depends(get_db)
):
    """
    Generate an AI improvement plan based on current DORA metrics.

    If metrics are not provided in the request body, they are
    calculated automatically from the deploy_events table.
    """
    # If metrics were passed in the request, use those.
    # Otherwise calculate them from the database.
    if request.deploy_frequency is not None:
        metrics = {
            "deploy_frequency": request.deploy_frequency,
            "lead_time_hours": request.lead_time_hours or 0,
            "change_failure_rate": request.change_failure_rate or 0,
            "mttr_minutes": request.mttr_minutes or 0,
            "performance_band": "Unknown",
        }
    else:
        # Fetch all deploy events and calculate DORA via Pandas
        events = db.query(DeployEvent).all()
        if not events:
            raise HTTPException(status_code=400, detail="No deploy events found. Seed the database first.")
        metrics = calculate_dora_metrics(events)

    result = await ai_service.generate_dora_plan(
        deploy_frequency=metrics["deploy_frequency"],
        lead_time_hours=metrics["lead_time_hours"],
        change_failure_rate=metrics["change_failure_rate"],
        mttr_minutes=metrics["mttr_minutes"],
        performance_band=metrics.get("performance_band", "Unknown"),
    )

    return AIResponse(
        result=result,
        model_used=f"ollama/{ai_service.settings.OLLAMA_MODEL}",
    )


@router.post("/cab-brief", response_model=AIResponse)
async def cab_brief(
    request: AICABBriefRequest,
    db: Session = Depends(get_db)
):
    """
    Generate a CAB meeting brief from all pending/active releases.
    """
    from backend.models import ReleaseStatus, BlockerSeverity

    # Get all active releases (not yet deployed)
    active_releases = db.query(Release).filter(
        Release.status.in_([
            ReleaseStatus.IN_PROGRESS,
            ReleaseStatus.QA_REVIEW,
            ReleaseStatus.CAB_PENDING,
            ReleaseStatus.PLANNING,
        ])
    ).all()

    if not active_releases:
        raise HTTPException(status_code=400, detail="No active releases found for CAB brief.")

    # Build the change request list
    change_requests = []
    for release in active_releases:
        high_blockers = [b for b in release.blockers if b.severity == BlockerSeverity.HIGH]
        risk = "High" if high_blockers else ("Medium" if release.blockers else "Low")

        change_requests.append({
            "title": f"{release.name} {release.version}",
            "risk": risk,
            "requester": release.owner,
            "status": release.status.value,
        })

    result = await ai_service.generate_cab_brief(
        change_requests=change_requests,
        week_label=request.week_label or "This Week",
    )

    return AIResponse(
        result=result,
        model_used=f"ollama/{ai_service.settings.OLLAMA_MODEL}",
    )


@router.post("/sprint-summary", response_model=AIResponse)
async def sprint_summary(db: Session = Depends(get_db)):
    """
    Generate a quick AI health summary of the current sprint.
    Used on the dashboard overview page.
    """
    releases = db.query(Release).all()
    if not releases:
        raise HTTPException(status_code=400, detail="No releases found.")

    release_data = [
        {
            "name": r.name,
            "version": r.version,
            "status": r.status.value,
            "blocker_count": len([b for b in r.blockers if b.status.value == "open"]),
        }
        for r in releases
    ]

    result = await ai_service.generate_sprint_summary(release_data)

    return AIResponse(
        result=result,
        model_used=f"ollama/{ai_service.settings.OLLAMA_MODEL}",
    )


@router.get("/status")
async def ai_status():
    """
    Check if Ollama is running and the model is available.
    Useful for debugging — call this first if AI endpoints aren't working.
    """
    import httpx
    from backend.config import settings

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            response = await client.get(f"{settings.OLLAMA_BASE_URL}/api/tags")
            models = response.json().get("models", [])
            model_names = [m["name"] for m in models]
            target_available = any(settings.OLLAMA_MODEL in m for m in model_names)

            return {
                "ollama_running": True,
                "available_models": model_names,
                "target_model": settings.OLLAMA_MODEL,
                "target_model_available": target_available,
                "status": "ready" if target_available else f"Model '{settings.OLLAMA_MODEL}' not found. Run: ollama pull {settings.OLLAMA_MODEL}",
            }
    except Exception:
        return {
            "ollama_running": False,
            "status": "Ollama not running. Start with: ollama serve",
        }
