# dashboard/pages/4_Pipeline.py
#
# CI/CD Pipeline page — shows the pipeline stages for each release
# with a visual step-by-step view and the ability to advance it (demo mode).

import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.api_client import (
    get_releases, get_pipeline, get_pipeline_summary, advance_pipeline
)

st.set_page_config(page_title="Pipeline · ReleasePilot", page_icon="⚙", layout="wide")

st.title("⚙ CI/CD Pipeline")
st.caption("Jenkins / GitHub Actions pipeline status per release")
st.divider()

# ── Release selector ──────────────────────────────────────────────────────────
releases = get_releases()
if not releases:
    st.warning("No releases found.")
    st.stop()

release_options = {f"{r['name']} {r['version']}": r["id"] for r in releases}
selected_name = st.selectbox("Select release", list(release_options.keys()))
selected_id   = release_options[selected_name]

# ── Pipeline summary ──────────────────────────────────────────────────────────
summary = get_pipeline_summary(selected_id)
if summary:
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Total Stages",  summary["total_stages"])
    c2.metric("✅ Completed",   summary["completed"])
    c3.metric("❌ Failed",      summary["failed"])
    c4.metric("⏳ Pending",     summary["pending"])

    if summary.get("current_stage"):
        st.info(f"⟳ Currently running: **{summary['current_stage']}**")

    total_dur = summary.get("total_duration_seconds", 0)
    if total_dur:
        mins = total_dur // 60
        secs = total_dur % 60
        st.caption(f"⏱ Total elapsed time: {mins}m {secs}s")

st.divider()

# ── Visual pipeline ───────────────────────────────────────────────────────────
st.subheader("Pipeline Stages")

stages = get_pipeline(selected_id)

STATUS_CONFIG = {
    "success": {"icon": "✅", "color": "#00e5a0", "bg": "#0d3321"},
    "running":  {"icon": "⟳", "color": "#f6c90e", "bg": "#3d2e00"},
    "failed":   {"icon": "❌", "color": "#fc8181", "bg": "#3d0d0d"},
    "pending":  {"icon": "○",  "color": "#718096", "bg": "#1a202c"},
    "skipped":  {"icon": "⏭",  "color": "#718096", "bg": "#1a202c"},
}

if stages:
    # Draw stages in a grid — 4 per row max
    chunk_size = 4
    for i in range(0, len(stages), chunk_size):
        chunk = stages[i:i+chunk_size]
        cols = st.columns(len(chunk))

        for col, stage in zip(cols, chunk):
            cfg = STATUS_CONFIG.get(stage["status"], STATUS_CONFIG["pending"])
            with col:
                # Use st.container with markdown for a styled card
                st.markdown(
                    f"""
                    <div style="background:{cfg['bg']};border:1px solid {cfg['color']}33;
                    border-radius:8px;padding:14px;text-align:center;margin-bottom:8px;">
                        <div style="font-size:24px">{cfg['icon']}</div>
                        <div style="font-size:13px;font-weight:600;color:{cfg['color']};margin-top:6px;">
                            {stage['stage_name']}
                        </div>
                        <div style="font-size:11px;color:#718096;margin-top:4px;">
                            {f"{stage['duration_seconds']}s" if stage.get('duration_seconds') else stage['status']}
                        </div>
                    </div>
                    """,
                    unsafe_allow_html=True
                )

        # Add arrow between rows
        if i + chunk_size < len(stages):
            st.markdown("<div style='text-align:center;color:#718096;margin:4px 0'>↓</div>", unsafe_allow_html=True)

else:
    st.info("No pipeline stages found for this release.")

st.divider()

# ── Demo controls ─────────────────────────────────────────────────────────────
st.subheader("🎮 Demo Controls")
st.caption("Advance the pipeline to simulate a Jenkins/GitHub Actions run")

col_btn, col_info = st.columns([1, 3])
with col_btn:
    if st.button("▶ Advance Pipeline", type="primary"):
        result = advance_pipeline(selected_id)
        if result:
            st.success(f"▶ {result.get('message','')} — Now running: **{result.get('now_running','')}**")
            st.rerun()

with col_info:
    st.info("💡 Click 'Advance Pipeline' to simulate each stage completing. "
            "In production, Jenkins/GitHub Actions would call the API automatically via webhooks.")

# ── Stage detail table ────────────────────────────────────────────────────────
if stages:
    st.divider()
    with st.expander("📋 Stage Details Table"):
        import pandas as pd
        table = [{
            "Order":    s["stage_order"],
            "Stage":    s["stage_name"],
            "Status":   STATUS_CONFIG.get(s["status"],{}).get("icon","○") + " " + s["status"],
            "Duration": f"{s['duration_seconds']}s" if s.get("duration_seconds") else "—",
            "Started":  s.get("started_at","")[:16] if s.get("started_at") else "—",
            "Finished": s.get("finished_at","")[:16] if s.get("finished_at") else "—",
        } for s in stages]
        st.dataframe(pd.DataFrame(table), use_container_width=True, hide_index=True)
