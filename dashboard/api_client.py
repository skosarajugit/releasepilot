# dashboard/api_client.py
#
# This file is the bridge between Streamlit and FastAPI.
# Every dashboard page imports this to fetch data.
#
# Why a separate file?
#   - Keeps all API URLs in one place
#   - If the backend URL changes, you update it here only
#   - Each function handles errors gracefully so the dashboard
#     doesn't crash if the backend is down

import httpx
import streamlit as st

# Read backend URL from environment, default to localhost
import os
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Timeout for regular calls (seconds)
TIMEOUT = 30
# Timeout for AI calls — TinyLlama can be slow
AI_TIMEOUT = 120


def _get(path: str, params: dict = None) -> dict | list | None:
    """
    Internal helper — makes a GET request to the FastAPI backend.
    Returns parsed JSON or None if the request fails.
    Shows a Streamlit error message if something goes wrong.
    """
    try:
        response = httpx.get(
            f"{BACKEND_URL}{path}",
            params=params,
            timeout=TIMEOUT,
            follow_redirects=True
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to backend. Make sure FastAPI is running: `uvicorn backend.main:app --reload`")
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"❌ API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None


def _post(path: str, body: dict = None, timeout: int = TIMEOUT) -> dict | None:
    """Internal helper — makes a POST request"""
    try:
        response = httpx.post(
            f"{BACKEND_URL}{path}",
            json=body or {},
            timeout=timeout,
            follow_redirects=True
        )
        response.raise_for_status()
        return response.json()
    except httpx.ConnectError:
        st.error("❌ Cannot connect to backend. Is FastAPI running?")
        return None
    except httpx.HTTPStatusError as e:
        st.error(f"❌ API error {e.response.status_code}: {e.response.text}")
        return None
    except Exception as e:
        st.error(f"❌ Unexpected error: {str(e)}")
        return None


# ── Releases ──────────────────────────────────────────────────────────────────

def get_releases(status: str = None) -> list:
    """Fetch all releases, optionally filtered by status"""
    params = {"status": status} if status else None
    return _get("/releases", params=params) or []


def get_release(release_id: int) -> dict | None:
    """Fetch a single release with all commits, blockers, pipeline stages"""
    return _get(f"/releases/{release_id}")


def get_release_commits(release_id: int) -> dict | None:
    """Fetch commits for a release"""
    return _get(f"/releases/{release_id}/commits")


# ── Blockers ──────────────────────────────────────────────────────────────────

def get_blockers(status: str = None, severity: str = None) -> list:
    """Fetch blockers, optionally filtered"""
    params = {}
    if status:   params["status"] = status
    if severity: params["severity"] = severity
    return _get("/blockers", params=params) or []


def resolve_blocker(blocker_id: int) -> dict | None:
    """Mark a blocker as resolved"""
    return _post(f"/blockers/{blocker_id}/resolve")


def escalate_blocker(blocker_id: int) -> dict | None:
    """Mark a blocker as escalated"""
    return _post(f"/blockers/{blocker_id}/escalate")


# ── Pipeline ──────────────────────────────────────────────────────────────────

def get_pipeline(release_id: int) -> list:
    """Fetch all pipeline stages for a release"""
    return _get(f"/pipeline/release/{release_id}") or []


def get_pipeline_summary(release_id: int) -> dict | None:
    """Fetch pipeline health summary"""
    return _get(f"/pipeline/release/{release_id}/summary")


def advance_pipeline(release_id: int) -> dict | None:
    """Advance pipeline to next stage (demo)"""
    return _post(f"/pipeline/release/{release_id}/advance")


# ── Metrics ───────────────────────────────────────────────────────────────────

def get_dora_metrics() -> dict | None:
    """Fetch the four DORA metrics"""
    return _get("/metrics/dora")


def get_deploy_trend(weeks: int = 12) -> dict | None:
    """Fetch weekly deploy trend data for charts"""
    return _get("/metrics/deploy-trend", params={"weeks": weeks})


# ── AI ────────────────────────────────────────────────────────────────────────

def ai_release_notes(release_id: int, audience: str = "engineering") -> str:
    """Generate AI release notes for a release"""
    result = _post(
        "/ai/release-notes",
        body={"release_id": release_id, "audience": audience},
        timeout=AI_TIMEOUT
    )
    return result["result"] if result else "AI service unavailable."


def ai_triage_blocker(blocker_id: int) -> str:
    """Get AI triage suggestion for a blocker"""
    result = _post(
        "/ai/triage",
        body={"blocker_id": blocker_id},
        timeout=AI_TIMEOUT
    )
    return result["result"] if result else "AI service unavailable."


def ai_dora_plan() -> str:
    """Get AI DORA improvement plan"""
    result = _post("/ai/dora-plan", timeout=AI_TIMEOUT)
    return result["result"] if result else "AI service unavailable."


def ai_cab_brief(week_label: str = None) -> str:
    """Get AI CAB meeting brief"""
    body = {"week_label": week_label} if week_label else {}
    result = _post("/ai/cab-brief", body=body, timeout=AI_TIMEOUT)
    return result["result"] if result else "AI service unavailable."


def ai_sprint_summary() -> str:
    """Get AI sprint health summary"""
    result = _post("/ai/sprint-summary", timeout=AI_TIMEOUT)
    return result["result"] if result else "AI service unavailable."


def get_ai_status() -> dict:
    """Check if Ollama is running"""
    return _get("/ai/status") or {"ollama_running": False, "status": "Unknown"}
