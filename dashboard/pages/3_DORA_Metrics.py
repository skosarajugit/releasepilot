# dashboard/pages/3_DORA_Metrics.py
#
# DORA Metrics page — shows the four key metrics with charts
# and an AI-generated improvement plan.
#
# Pandas does the heavy lifting in metrics_service.py (backend).
# This page just visualizes what the API returns.

import streamlit as st
import pandas as pd
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.api_client import get_dora_metrics, get_deploy_trend, ai_dora_plan

st.set_page_config(page_title="DORA Metrics · ReleasePilot", page_icon="📊", layout="wide")

st.title("📊 DORA Metrics")
st.caption("DevOps Research & Assessment — measuring software delivery performance")
st.divider()

dora = get_dora_metrics()

if not dora:
    st.error("Could not load DORA metrics. Is the backend running?")
    st.stop()

# ── Performance band banner ───────────────────────────────────────────────────
band = dora.get("performance_band", "Unknown")
band_config = {
    "Elite":  ("🏆", "green",  "Your team is performing at the highest DORA level."),
    "High":   ("⭐", "blue",   "Strong performance — a few improvements will get you to Elite."),
    "Medium": ("📈", "orange", "Good foundation — focus on automation and test coverage."),
    "Low":    ("⚠️", "red",    "Significant improvement needed across delivery practices."),
}
emoji, color, message = band_config.get(band, ("❓", "gray", ""))

if color == "green":   st.success(f"{emoji} **{band} Performance** — {message}")
elif color == "blue":  st.info(f"{emoji} **{band} Performance** — {message}")
elif color == "orange":st.warning(f"{emoji} **{band} Performance** — {message}")
else:                  st.error(f"{emoji} **{band} Performance** — {message}")

st.divider()

# ── Four metric cards ─────────────────────────────────────────────────────────
st.subheader("Current Metrics")

col1, col2, col3, col4 = st.columns(4)

# Helper to show Elite/High/Medium/Low band per metric
def metric_band(value, thresholds: dict) -> str:
    """Returns the band label given a value and threshold dict"""
    for band_name, (low, high) in thresholds.items():
        if low <= value < high:
            return band_name
    return "Low"

with col1:
    v = dora["deploy_frequency"]
    band_df = "Elite" if v >= 1 else ("High" if v >= 0.14 else ("Medium" if v >= 0.03 else "Low"))
    delta_color = "normal" if band_df in ("Elite","High") else "inverse"
    st.metric("🚀 Deploy Frequency", f"{v}/day", delta=f"{band_df} tier", delta_color=delta_color)
    # Progress bar showing how close to Elite (1.0/day)
    progress = min(v / 5.0, 1.0)   # Scale to 5/day max for display
    st.progress(progress)
    st.caption("Elite: ≥ 1/day  |  High: ≥ weekly")

with col2:
    v = dora["lead_time_hours"]
    band_lt = "Elite" if v < 1 else ("High" if v < 168 else ("Medium" if v < 720 else "Low"))
    st.metric("⏱ Lead Time", f"{v}h", delta=f"{band_lt} tier")
    progress = max(0, 1.0 - (v / 168))  # Inverse — lower is better
    st.progress(min(progress, 1.0))
    st.caption("Elite: < 1h  |  High: < 1 week")

with col3:
    v = dora["change_failure_rate"]
    band_cfr = "Elite" if v <= 5 else ("High" if v <= 10 else ("Medium" if v <= 15 else "Low"))
    st.metric("💥 Change Failure Rate", f"{v}%", delta=f"{band_cfr} tier", delta_color="inverse" if v > 5 else "normal")
    progress = max(0, 1.0 - (v / 20))
    st.progress(min(progress, 1.0))
    st.caption("Elite: ≤ 5%  |  High: ≤ 10%")

with col4:
    v = dora["mttr_minutes"]
    band_mttr = "Elite" if v <= 60 else ("High" if v <= 1440 else ("Medium" if v <= 10080 else "Low"))
    st.metric("🔧 MTTR", f"{v:.0f} min", delta=f"{band_mttr} tier")
    progress = max(0, 1.0 - (v / 1440))
    st.progress(min(progress, 1.0))
    st.caption("Elite: ≤ 60 min  |  High: ≤ 1 day")

# ── Stats row ─────────────────────────────────────────────────────────────────
st.divider()
s1, s2 = st.columns(2)
s1.info(f"📦 **{dora['total_deploys']}** total deploys analyzed over **{dora['period_days']}** days")
s2.info(f"📅 Rolling data from the last **{dora['period_days']}** days of deploy history")

st.divider()

# ── Deploy trend chart ────────────────────────────────────────────────────────
st.subheader("📈 Deploy Trends")

trend = get_deploy_trend(weeks=12)
if trend and trend.get("data"):
    df = pd.DataFrame(trend["data"])

    tab1, tab2, tab3 = st.tabs(["Weekly Deploys", "Success Rate", "Combined"])

    with tab1:
        st.bar_chart(df.set_index("week")[["total"]], color="#00e5a0")

    with tab2:
        st.line_chart(df.set_index("week")[["success_rate"]], color="#0090ff")

    with tab3:
        # Show both on the same chart
        st.line_chart(df.set_index("week")[["total", "success_rate"]])
        st.caption("Blue = deploy count  |  Red = success rate %")
else:
    st.info("No trend data available.")

st.divider()

# ── AI Improvement Plan ───────────────────────────────────────────────────────
st.subheader("✦ AI Improvement Plan")
st.caption("AI analyzes your metrics and recommends specific improvements")

plan_key = "dora_plan"
if plan_key not in st.session_state:
    st.session_state[plan_key] = None

if st.button("✦ Generate Improvement Plan", type="primary"):
    with st.spinner("AI is analyzing your DORA metrics... (15-30 seconds)"):
        st.session_state[plan_key] = ai_dora_plan()

if st.session_state[plan_key]:
    st.markdown(
        f'<div style="background:#0f1117;border:1px solid #00e5a0;border-radius:8px;'
        f'padding:16px;font-size:14px;line-height:1.7;color:#e2e8f0;">'
        f'{st.session_state[plan_key]}</div>',
        unsafe_allow_html=True
    )

# ── DORA reference table ──────────────────────────────────────────────────────
st.divider()
with st.expander("📖 DORA Performance Band Reference"):
    ref_data = {
        "Metric":          ["Deploy Frequency", "Lead Time", "Change Failure Rate", "MTTR"],
        "Elite":           ["Multiple/day",     "< 1 hour",  "0–5%",               "< 1 hour"],
        "High":            ["Weekly–daily",      "1d–1week",  "5–10%",              "< 1 day"],
        "Medium":          ["Monthly",           "1wk–1mo",   "10–15%",             "1day–1wk"],
        "Low":             ["< 6 months",        "> 6 months","> 15%",              "> 6 months"],
    }
    st.dataframe(pd.DataFrame(ref_data), use_container_width=True, hide_index=True)
