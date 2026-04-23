# dashboard/app.py
#
# Main entry point for the Streamlit dashboard.
# This is the first page users see — the Overview / Dashboard.
#
# To run:
#   streamlit run dashboard/app.py
#
# Streamlit works differently from regular Python:
#   - The entire script re-runs top to bottom every time a user
#     interacts with anything (clicks a button, changes a dropdown)
#   - st.session_state persists values between reruns
#   - @st.cache_data caches expensive API calls so they don't repeat

import streamlit as st

# ── Page config — must be the FIRST streamlit call ───────────────────────────
st.set_page_config(
    page_title="ReleasePilot",
    page_icon="🚀",
    layout="wide",                    # Use full browser width
    initial_sidebar_state="expanded"
)

import pandas as pd
#from dashboard.api_client import (
from api_client import (
    get_releases, get_dora_metrics, get_deploy_trend,
    get_blockers, ai_sprint_summary, get_ai_status
)

# ── Custom CSS ────────────────────────────────────────────────────────────────
# Streamlit has limited styling — we inject CSS to improve the look
st.markdown("""
<style>
    /* Reduce top padding */
    .block-container { padding-top: 1.5rem; }

    /* Metric cards */
    [data-testid="stMetric"] {
        background: #1a1f2e;
        border: 1px solid #2d3748;
        border-radius: 8px;
        padding: 16px;
    }
    [data-testid="stMetricLabel"] { font-size: 12px; color: #718096; }
    [data-testid="stMetricValue"] { font-size: 28px; }

    /* AI output box */
    .ai-box {
        background: #0f1117;
        border: 1px solid #00e5a0;
        border-radius: 8px;
        padding: 16px;
        font-size: 14px;
        line-height: 1.7;
        color: #e2e8f0;
    }

    /* Status pills */
    .pill-green  { background:#0d3321; color:#00e5a0; padding:3px 10px; border-radius:12px; font-size:12px; }
    .pill-yellow { background:#3d2e00; color:#f6c90e; padding:3px 10px; border-radius:12px; font-size:12px; }
    .pill-red    { background:#3d0d0d; color:#fc8181; padding:3px 10px; border-radius:12px; font-size:12px; }
    .pill-blue   { background:#0d1f3d; color:#63b3ed; padding:3px 10px; border-radius:12px; font-size:12px; }
    .pill-gray   { background:#1a202c; color:#718096; padding:3px 10px; border-radius:12px; font-size:12px; }
</style>
""", unsafe_allow_html=True)


# ── Helper: status color ──────────────────────────────────────────────────────
STATUS_COLORS = {
    "deployed":    "🟢",
    "in_progress": "🟡",
    "qa_review":   "🔵",
    "planning":    "⚪",
    "cab_pending": "🟠",
    "rolled_back": "🔴",
}
SEVERITY_COLORS = {
    "high":   "🔴",
    "medium": "🟡",
    "low":    "🔵",
}


# ── Page Header ───────────────────────────────────────────────────────────────
col_title, col_status = st.columns([3, 1])
with col_title:
    st.title("🚀 ReleasePilot")
    st.caption("AI-powered Release Manager Dashboard")

with col_status:
    ai_status = get_ai_status()
    if ai_status.get("ollama_running"):
        st.success(f"✦ AI Ready · {ai_status.get('target_model', 'unknown')}")
    else:
        st.warning("⚠ Ollama offline — run `ollama serve`")

st.divider()

# ── DORA Metrics Row ──────────────────────────────────────────────────────────
st.subheader("📊 DORA Metrics")

dora = get_dora_metrics()
if dora:
    col1, col2, col3, col4, col5 = st.columns(5)

    with col1:
        st.metric(
            label="Deploy Frequency",
            value=f"{dora['deploy_frequency']}/day",
            delta="Elite tier" if dora['deploy_frequency'] >= 1 else "Below target",
        )
    with col2:
        st.metric(
            label="Lead Time",
            value=f"{dora['lead_time_hours']}h",
            delta="Elite" if dora['lead_time_hours'] < 1 else f"Target: <1h",
        )
    with col3:
        st.metric(
            label="Change Failure Rate",
            value=f"{dora['change_failure_rate']}%",
            delta="Target: <5%" if dora['change_failure_rate'] > 5 else "On target",
            delta_color="inverse",
        )
    with col4:
        st.metric(
            label="MTTR",
            value=f"{dora['mttr_minutes']:.0f} min",
            delta="Elite" if dora['mttr_minutes'] < 60 else "Above target",
        )
    with col5:
        band = dora.get("performance_band", "Unknown")
        band_emoji = {"Elite": "🏆", "High": "⭐", "Medium": "📈", "Low": "⚠️"}.get(band, "")
        st.metric(label="Performance Band", value=f"{band_emoji} {band}")
else:
    st.warning("Could not load DORA metrics. Is the backend running?")

st.divider()

# ── Two column layout: Releases + Blockers ────────────────────────────────────
col_left, col_right = st.columns([3, 2])

with col_left:
    st.subheader("📦 Active Releases")
    releases = get_releases()

    if releases:
        for r in releases:
            status_icon = STATUS_COLORS.get(r["status"], "⚪")
            with st.expander(f"{status_icon} {r['name']} {r['version']} — {r['owner']}"):
                c1, c2, c3 = st.columns(3)
                c1.write(f"**Status:** {r['status'].replace('_',' ').title()}")
                c2.write(f"**Target:** {r['target_date'][:10] if r.get('target_date') else 'TBD'}")
                c3.write(f"**ID:** `{r['id']}`")

                # Link to detailed page
                st.caption(f"→ See full details in the **Releases** page")
    else:
        st.info("No releases found.")

with col_right:
    st.subheader("🚧 Open Blockers")
    blockers = get_blockers(status="open")

    if blockers:
        for b in blockers[:5]:   # Show top 5
            sev_icon = SEVERITY_COLORS.get(b["severity"], "⚪")
            st.markdown(f"{sev_icon} **{b['title'][:55]}**")
            st.caption(f"Release #{b['release_id']} · {b['severity'].upper()} · {b.get('assigned_to','Unassigned')}")
            st.divider()

        if len(blockers) > 5:
            st.caption(f"+ {len(blockers) - 5} more — see Blockers page")
    else:
        st.success("✅ No open blockers!")

st.divider()

# ── Deploy Trend Chart ────────────────────────────────────────────────────────
st.subheader("📈 Deploy Trend (Last 12 Weeks)")

trend = get_deploy_trend(weeks=12)
if trend and trend.get("data"):
    df = pd.DataFrame(trend["data"])

    # Two charts side by side
    chart_col1, chart_col2 = st.columns(2)

    with chart_col1:
        st.markdown("**Weekly Deploy Count**")
        # st.bar_chart expects a DataFrame with the index as x-axis
        df_chart = df.set_index("week")[["total"]]
        st.bar_chart(df_chart, color="#00e5a0")

    with chart_col2:
        st.markdown("**Success Rate % per Week**")
        df_success = df.set_index("week")[["success_rate"]]
        st.line_chart(df_success, color="#0090ff")
else:
    st.info("No deploy trend data available.")

st.divider()

# ── AI Sprint Summary ─────────────────────────────────────────────────────────
st.subheader("✦ AI Sprint Summary")
st.caption("Powered by Ollama (local AI — free)")

if "sprint_summary" not in st.session_state:
    st.session_state.sprint_summary = None

col_btn, col_empty = st.columns([1, 4])
with col_btn:
    if st.button("⚡ Generate Summary", type="primary"):
        with st.spinner("AI is thinking... (this takes 15-30 seconds on TinyLlama)"):
            st.session_state.sprint_summary = ai_sprint_summary()

if st.session_state.sprint_summary:
    st.markdown(
        f'<div class="ai-box">{st.session_state.sprint_summary}</div>',
        unsafe_allow_html=True
    )
