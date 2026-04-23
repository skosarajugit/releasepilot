# backend/routers/notifications.py
#
# Endpoints for triggering Slack notifications.
# In production these would be called automatically by:
#   - Jenkins webhooks when a deploy starts/finishes
#   - The blockers router when a high-severity blocker is created
#   - A scheduled job for the daily digest
#
# For the portfolio demo, we expose them as manual endpoints
# so you can trigger them from /docs or the Streamlit dashboard.

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional

from backend.database import get_db
from backend.models import Release, Blocker, DeployEvent, ReleaseStatus
from backend.services import slack_service

router = APIRouter()


# ── Request schemas ───────────────────────────────────────────────────────────

class DeployNotifyRequest(BaseModel):
    release_id: int
    environment: str = "production"
    event: str = "started"          # started | success | failed
    reason: str = None              # Only used for failed events
    duration_minutes: float = None  # Only used for success events


class BlockerNotifyRequest(BaseModel):
    blocker_id: int


class DigestRequest(BaseModel):
    pass   # No params needed — fetches all releases automatically


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/deploy")
async def notify_deploy(request: DeployNotifyRequest, db: Session = Depends(get_db)):
    """
    Send a Slack notification for a deployment event.

    event options:
      "started"  → deploy has begun
      "success"  → deploy completed successfully
      "failed"   → deploy failed

    Example:
    POST /notifications/deploy
    { "release_id": 1, "environment": "production", "event": "started" }
    """
    release = db.query(Release).filter(Release.id == request.release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {request.release_id} not found")

    if request.event == "started":
        await slack_service.notify_deploy_started(
            release_name=release.name,
            version=release.version,
            environment=request.environment,
            owner=release.owner,
        )
    elif request.event == "success":
        await slack_service.notify_deploy_success(
            release_name=release.name,
            version=release.version,
            environment=request.environment,
            duration_minutes=request.duration_minutes,
        )
    elif request.event == "failed":
        await slack_service.notify_deploy_failed(
            release_name=release.name,
            version=release.version,
            environment=request.environment,
            reason=request.reason,
        )
    else:
        raise HTTPException(status_code=400, detail="event must be: started | success | failed")

    return {"sent": True, "event": request.event, "release": f"{release.name} {release.version}"}


@router.post("/blocker")
async def notify_blocker(request: BlockerNotifyRequest, db: Session = Depends(get_db)):
    """
    Send a Slack notification for a flagged blocker.
    Includes AI suggestion if one has been generated.
    """
    blocker = db.query(Blocker).filter(Blocker.id == request.blocker_id).first()
    if not blocker:
        raise HTTPException(status_code=404, detail=f"Blocker {request.blocker_id} not found")

    release = db.query(Release).filter(Release.id == blocker.release_id).first()
    release_name = f"{release.name} {release.version}" if release else "Unknown Release"

    await slack_service.notify_blocker_flagged(
        blocker_title=blocker.title,
        release_name=release_name,
        severity=blocker.severity.value,
        assigned_to=blocker.assigned_to,
        ai_suggestion=blocker.ai_suggestion,
    )

    return {"sent": True, "blocker": blocker.title}


@router.post("/digest")
async def send_daily_digest(db: Session = Depends(get_db)):
    """
    Send the daily release status digest to Slack.
    Shows all releases and their current status.
    Call this from a cron job or scheduled task for daily standups.
    """
    releases = db.query(Release).all()
    if not releases:
        raise HTTPException(status_code=400, detail="No releases found.")

    summary = [
        {"name": r.name, "version": r.version, "status": r.status.value, "owner": r.owner}
        for r in releases
    ]

    await slack_service.notify_release_summary(summary)
    return {"sent": True, "release_count": len(summary)}


@router.post("/cab-approved/{release_id}")
async def notify_cab_approved(
    release_id: int,
    deploy_window: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Send CAB approval notification for a release.
    """
    release = db.query(Release).filter(Release.id == release_id).first()
    if not release:
        raise HTTPException(status_code=404, detail=f"Release {release_id} not found")

    await slack_service.notify_cab_approved(
        release_name=release.name,
        version=release.version,
        deploy_window=deploy_window,
    )
    return {"sent": True, "release": f"{release.name} {release.version}"}


#@router.get("/test")
@router.post("/test")

async def test_notification():
    """
    Send a test notification to verify Slack is configured.
    Use this first to make sure your webhook URL works.
    """
    from datetime import datetime
    from backend.services.slack_service import send_slack_message

    await send_slack_message(
        blocks=[
            {
                "type": "header",
                "text": {"type": "plain_text", "text": "🧪 ReleasePilot Test Notification"}
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f"Your Slack integration is working! ✅\nSent at {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"
                }
            }
        ],
        text="ReleasePilot test notification"
    )
    return {
        "sent": True,
        "webhook_configured": bool(__import__('backend.config', fromlist=['settings']).settings.SLACK_WEBHOOK_URL),
        "message": "Check your terminal output if no webhook is configured"
    }
