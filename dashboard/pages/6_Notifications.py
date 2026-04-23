# dashboard/pages/6_Notifications.py
#
# Notifications page — trigger Slack notifications manually from the dashboard.
# In production these fire automatically from pipeline webhooks.
# Here you can trigger them to demo the Slack integration.

import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

import httpx
from dashboard.api_client import get_releases, BACKEND_URL

st.set_page_config(page_title="Notifications · ReleasePilot", page_icon="📣", layout="wide")

st.title("📣 Slack Notifications")
st.caption("Trigger release notifications — fires to Slack or logs to console if no webhook configured")
st.divider()

# ── Configuration status ──────────────────────────────────────────────────────
st.subheader("⚙ Configuration")

col1, col2 = st.columns(2)
with col1:
    webhook_url = os.getenv("SLACK_WEBHOOK_URL", "")
    if webhook_url:
        st.success("✅ Slack webhook configured — notifications go to Slack")
    else:
        st.info("ℹ️ No webhook configured — notifications print to the **backend terminal**")
        st.caption("Set SLACK_WEBHOOK_URL in your .env file to send to real Slack")

with col2:
    st.markdown("""
    **To get a Slack webhook URL:**
    1. Go to https://api.slack.com/apps
    2. Create New App → From Scratch
    3. Incoming Webhooks → Activate
    4. Add New Webhook to Workspace
    5. Copy the URL into your `.env` file
    """)

st.divider()


def post_notification(path: str, body: dict) -> dict | None:
    """Helper to call notification endpoints"""
    try:
        #response = httpx.post(f"{BACKEND_URL}{path}", json=body, timeout=15)
        response = httpx.post(f"{BACKEND_URL}{path}", json=body, timeout=15, follow_redirects=True)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        st.error(f"Error: {e}")
        return None


# ── Test notification ─────────────────────────────────────────────────────────
st.subheader("🧪 Test Connection")
if st.button("Send Test Notification"):
    result = post_notification("/notifications/test", {})
    if result:
        st.success("✅ Test notification sent! Check your Slack channel or backend terminal.")

st.divider()

# ── Deploy notifications ──────────────────────────────────────────────────────
st.subheader("🚀 Deploy Notifications")

releases = get_releases()
if releases:
    release_options = {f"{r['name']} {r['version']}": r["id"] for r in releases}

    col_select, col_env, col_event = st.columns(3)
    with col_select:
        selected_release = st.selectbox("Release", list(release_options.keys()), key="deploy_release")
    with col_env:
        environment = st.selectbox("Environment", ["production", "staging"], key="deploy_env")
    with col_event:
        event = st.selectbox("Event", ["started", "success", "failed"], key="deploy_event")

    extra_col1, extra_col2 = st.columns(2)
    with extra_col1:
        duration = st.number_input("Duration (min, for success)", min_value=0.0, value=5.0, step=0.5) if event == "success" else None
    with extra_col2:
        reason = st.text_input("Failure reason (for failed)") if event == "failed" else None

    if st.button("📤 Send Deploy Notification", type="primary"):
        body = {
            "release_id": release_options[selected_release],
            "environment": environment,
            "event": event,
        }
        if duration: body["duration_minutes"] = duration
        if reason:   body["reason"] = reason

        result = post_notification("/notifications/deploy/", body)
        if result:
            st.success(f"✅ Sent '{event}' notification for {selected_release}")

st.divider()

# ── Blocker notification ──────────────────────────────────────────────────────
st.subheader("🚧 Blocker Flagged Notification")

# Get open blockers
try:
    response = httpx.get(f"{BACKEND_URL}/blockers?status=open", timeout=10)
    blockers = response.json() if response.status_code == 200 else []
except:
    blockers = []

if blockers:
    blocker_options = {f"[{b['severity'].upper()}] {b['title'][:50]}": b["id"] for b in blockers}
    selected_blocker = st.selectbox("Select Blocker", list(blocker_options.keys()))

    if st.button("📤 Send Blocker Notification"):
        result = post_notification("/notifications/blocker", {
            "blocker_id": blocker_options[selected_blocker]
        })
        if result:
            st.success("✅ Blocker notification sent!")
else:
    st.info("No open blockers found.")

st.divider()

# ── Daily digest ──────────────────────────────────────────────────────────────
st.subheader("📦 Daily Release Digest")
st.caption("Sends a summary of all release statuses — schedule this for end-of-day standup")

if st.button("📤 Send Daily Digest"):
    result = post_notification("/notifications/digest", {})
    if result:
        st.success(f"✅ Digest sent for {result.get('release_count', 0)} releases!")
