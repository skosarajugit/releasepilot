# backend/routers/metrics.py
#
# Endpoints for DORA metrics and deploy trend data.
#
# GET /metrics/dora          → the four DORA metrics
# GET /metrics/deploy-trend  → weekly deploy counts for charts

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from backend.database import get_db
from backend.models import DeployEvent
from backend.schemas import DORAMetrics
from backend.services.metrics_service import calculate_dora_metrics, calculate_deploy_trend

router = APIRouter()


@router.get("/dora", response_model=DORAMetrics)
def get_dora_metrics(db: Session = Depends(get_db)):
    """
    Calculate and return the four DORA metrics from all deploy events.

    The Pandas calculations happen in metrics_service.py —
    this endpoint just fetches the data and calls that service.
    """
    events = db.query(DeployEvent).all()
    metrics = calculate_dora_metrics(events)
    return metrics


@router.get("/deploy-trend")
def get_deploy_trend(weeks: int = 12, db: Session = Depends(get_db)):
    """
    Get weekly deploy counts for the past N weeks.
    Used by Streamlit to draw trend charts.

    Example response:
    [
        {"week": "Jan 28", "total": 24, "success_rate": 95.8},
        {"week": "Feb 04", "total": 31, "success_rate": 100.0},
        ...
    ]
    """
    events = db.query(DeployEvent).all()
    trend = calculate_deploy_trend(events, weeks=weeks)
    return {"weeks": weeks, "data": trend}
