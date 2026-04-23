# backend/services/metrics_service.py
#
# This file calculates the four DORA metrics using Pandas.
#
# DORA = DevOps Research and Assessment
# The four metrics measure software delivery performance:
#
#   1. Deployment Frequency   → How often do you deploy to production?
#   2. Lead Time for Changes  → How long from commit to running in prod?
#   3. Change Failure Rate    → What % of deployments cause a failure?
#   4. Mean Time to Recovery  → How long to recover from a failure?
#
# Pandas is used here because it's great at:
#   - Time-series calculations (rolling averages, resampling by day/week)
#   - Aggregating large numbers of events quickly
#   - Exporting results as dicts/JSON for the API

import pandas as pd
from typing import List
from backend.models import DeployEvent


def calculate_dora_metrics(events: List[DeployEvent]) -> dict:
    """
    Calculate all four DORA metrics from a list of DeployEvent records.

    Args:
        events: List of DeployEvent ORM objects from the database

    Returns:
        Dictionary with all four metrics + performance band
    """
    if not events:
        return _empty_metrics()

    # ── Convert ORM objects to a Pandas DataFrame ─────────────────────────────
    # A DataFrame is like a spreadsheet in Python — rows and columns.
    # Each deploy event becomes one row.
    df = pd.DataFrame([
        {
            "deployed_at":      e.deployed_at,
            "success":          e.success,
            "rolled_back":      e.rolled_back,
            "recovered_at":     e.recovered_at,
            "first_commit_at":  e.first_commit_at,
        }
        for e in events
    ])

    # Convert string/object columns to proper datetime types
    df["deployed_at"]     = pd.to_datetime(df["deployed_at"])
    df["recovered_at"]    = pd.to_datetime(df["recovered_at"])
    df["first_commit_at"] = pd.to_datetime(df["first_commit_at"])

    # Sort by deploy time (oldest first)
    df = df.sort_values("deployed_at").reset_index(drop=True)

    # How many days of data do we have?
    period_days = max((df["deployed_at"].max() - df["deployed_at"].min()).days, 1)

    # ── Metric 1: Deployment Frequency ───────────────────────────────────────
    # How many deploys per day on average?
    # resample("D") groups events by day, then we count per day, then average
    df_indexed = df.set_index("deployed_at")
    daily_counts = df_indexed.resample("D").size()   # Count deploys per day
    deploy_frequency = float(daily_counts.mean())    # Average across all days

    # ── Metric 2: Lead Time for Changes ──────────────────────────────────────
    # How many hours between the first commit and the deploy?
    # We only measure this where we have both timestamps
    lead_time_df = df.dropna(subset=["first_commit_at"])
    if len(lead_time_df) > 0:
        # timedelta / pd.Timedelta converts to a float number of hours
        lead_times = (
            lead_time_df["deployed_at"] - lead_time_df["first_commit_at"]
        ).dt.total_seconds() / 3600   # Convert seconds → hours
        lead_time_hours = float(lead_times.clip(lower=0).mean())  # No negative times
    else:
        lead_time_hours = 0.0

    # ── Metric 3: Change Failure Rate ────────────────────────────────────────
    # What % of deployments failed?
    total_deploys = len(df)
    failed_deploys = len(df[df["success"] == False])
    change_failure_rate = (failed_deploys / total_deploys * 100) if total_deploys > 0 else 0.0

    # ── Metric 4: Mean Time to Recovery (MTTR) ───────────────────────────────
    # For failed deploys that were recovered, how long did it take?
    failed_df = df[(df["success"] == False) & df["recovered_at"].notna()]
    if len(failed_df) > 0:
        recovery_times = (
            failed_df["recovered_at"] - failed_df["deployed_at"]
        ).dt.total_seconds() / 60   # Convert seconds → minutes
        mttr_minutes = float(recovery_times.clip(lower=0).mean())
    else:
        mttr_minutes = 0.0

    # ── Performance Band ──────────────────────────────────────────────────────
    # DORA defines four performance bands based on the metrics.
    # We assign the overall band based on the weakest metric.
    band = _calculate_performance_band(
        deploy_frequency, lead_time_hours, change_failure_rate, mttr_minutes
    )

    return {
        "deploy_frequency":     round(deploy_frequency, 2),
        "lead_time_hours":      round(lead_time_hours, 2),
        "change_failure_rate":  round(change_failure_rate, 2),
        "mttr_minutes":         round(mttr_minutes, 2),
        "performance_band":     band,
        "total_deploys":        total_deploys,
        "period_days":          period_days,
    }


def calculate_deploy_trend(events: List[DeployEvent], weeks: int = 12) -> list:
    """
    Calculate weekly deploy counts for trend charts.
    Returns a list of {week, count, success_rate} dicts.

    Used by the Streamlit dashboard to draw the sparkline chart.
    """
    if not events:
        return []

    df = pd.DataFrame([
        {"deployed_at": pd.to_datetime(e.deployed_at), "success": e.success}
        for e in events
    ])
    df = df.set_index("deployed_at").sort_index()

    # Get last N weeks of data
    cutoff = df.index.max() - pd.Timedelta(weeks=weeks)
    df = df[df.index >= cutoff]

    # Resample to weekly buckets
    weekly_total   = df.resample("W").size().rename("total")
    weekly_success = df[df["success"] == True].resample("W").size().rename("success")

    weekly = pd.concat([weekly_total, weekly_success], axis=1).fillna(0)
    weekly["success_rate"] = (weekly["success"] / weekly["total"] * 100).round(1)
    weekly["week"] = weekly.index.strftime("%b %d")

    return weekly[["week", "total", "success_rate"]].to_dict(orient="records")


def _calculate_performance_band(
    deploy_frequency: float,
    lead_time_hours: float,
    change_failure_rate: float,
    mttr_minutes: float
) -> str:
    """
    Determine DORA performance band based on official DORA thresholds.

    Elite:  Deploy multiple times/day, <1hr lead, <5% fail, <1hr MTTR
    High:   Deploy weekly-monthly, 1day-1wk lead, 5-10% fail, <1day MTTR
    Medium: Deploy monthly, 1wk-1mo lead, 10-15% fail, 1day-1wk MTTR
    Low:    Deploy <6mo, >6mo lead, >15% fail, >6mo MTTR
    """
    scores = []

    # Deploy Frequency
    if deploy_frequency >= 1:       scores.append("Elite")
    elif deploy_frequency >= 0.14:  scores.append("High")    # ~weekly
    elif deploy_frequency >= 0.03:  scores.append("Medium")  # ~monthly
    else:                           scores.append("Low")

    # Lead Time (hours)
    if lead_time_hours < 1:         scores.append("Elite")
    elif lead_time_hours < 168:     scores.append("High")    # <1 week
    elif lead_time_hours < 720:     scores.append("Medium")  # <1 month
    else:                           scores.append("Low")

    # Change Failure Rate (%)
    if change_failure_rate <= 5:    scores.append("Elite")
    elif change_failure_rate <= 10: scores.append("High")
    elif change_failure_rate <= 15: scores.append("Medium")
    else:                           scores.append("Low")

    # MTTR (minutes)
    if mttr_minutes <= 60:          scores.append("Elite")
    elif mttr_minutes <= 1440:      scores.append("High")    # <1 day
    elif mttr_minutes <= 10080:     scores.append("Medium")  # <1 week
    else:                           scores.append("Low")

    # Overall band = worst performing metric
    band_order = ["Elite", "High", "Medium", "Low"]
    worst = max(scores, key=lambda b: band_order.index(b))
    return worst


def _empty_metrics() -> dict:
    return {
        "deploy_frequency": 0.0,
        "lead_time_hours": 0.0,
        "change_failure_rate": 0.0,
        "mttr_minutes": 0.0,
        "performance_band": "Low",
        "total_deploys": 0,
        "period_days": 0,
    }
