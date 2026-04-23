# dashboard/pages/1_Releases.py
#
# The Releases page shows all releases in a table,
# lets you drill into individual releases, and generates AI release notes.
#
# Streamlit multipage apps work by putting files in a pages/ folder.
# The filename prefix (1_, 2_, etc.) sets the sidebar order.
# The rest of the filename becomes the page title.

import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.api_client import (
    get_releases, get_release, ai_release_notes
)

st.set_page_config(page_title="Releases · ReleasePilot", page_icon="📦", layout="wide")

st.title("📦 Releases")
st.caption("Track all active and completed releases")
st.divider()

# ── Status filter ─────────────────────────────────────────────────────────────
STATUS_OPTIONS = ["All", "planning", "in_progress", "qa_review", "cab_pending", "approved", "deployed"]
STATUS_ICONS   = {"planning":"⚪","in_progress":"🟡","qa_review":"🔵","cab_pending":"🟠","approved":"✅","deployed":"🟢","rolled_back":"🔴"}

selected_status = st.selectbox("Filter by status", STATUS_OPTIONS)
filter_val = None if selected_status == "All" else selected_status

releases = get_releases(status=filter_val)

# ── Release table ─────────────────────────────────────────────────────────────
if releases:
    # Build a simple summary table using st.dataframe
    import pandas as pd

    table_data = []
    for r in releases:
        table_data.append({
            "Status":      STATUS_ICONS.get(r["status"], "⚪") + " " + r["status"].replace("_"," ").title(),
            "Name":        r["name"],
            "Version":     r["version"],
            "Owner":       r["owner"],
            "Target Date": r["target_date"][:10] if r.get("target_date") else "TBD",
            "ID":          r["id"],
        })

    df = pd.DataFrame(table_data)
    st.dataframe(df, use_container_width=True, hide_index=True)
else:
    st.info("No releases found.")
    st.stop()

st.divider()

# ── Release detail drill-down ─────────────────────────────────────────────────
st.subheader("🔍 Release Detail")

release_options = {f"{r['name']} {r['version']}": r["id"] for r in releases}
selected_name = st.selectbox("Select a release to inspect", list(release_options.keys()))
selected_id   = release_options[selected_name]

detail = get_release(selected_id)

if detail:
    col1, col2, col3 = st.columns(3)
    col1.metric("Status",  detail["status"].replace("_"," ").title())
    col2.metric("Commits", len(detail.get("commits", [])))
    col3.metric("Blockers", len([b for b in detail.get("blockers",[]) if b["status"] == "open"]))

    # ── Commits tab ──────────────────────────────────────────────────────────
    tab_commits, tab_blockers, tab_pipeline, tab_ai = st.tabs([
        "📝 Commits", "🚧 Blockers", "⚙ Pipeline", "✦ AI Notes"
    ])

    with tab_commits:
        commits = detail.get("commits", [])
        if commits:
            for c in sorted(commits, key=lambda x: x.get("committed_at") or "", reverse=True):
                col_sha, col_msg = st.columns([1, 5])
                with col_sha:
                    st.code(c["sha"][:7], language=None)
                with col_msg:
                    type_badge = {"feat":"🟢","fix":"🔴","refactor":"🔵","chore":"⚪","test":"🟡"}.get(c.get("commit_type",""),"⚪")
                    st.write(f"{type_badge} {c['message']}")
                    st.caption(f"{c['author']} · {c.get('committed_at','')[:10]} · {c.get('jira_ticket','')}")
        else:
            st.info("No commits found for this release.")

    with tab_blockers:
        blockers = detail.get("blockers", [])
        if blockers:
            for b in blockers:
                sev_color = {"high":"🔴","medium":"🟡","low":"🔵"}.get(b["severity"],"⚪")
                status_icon = "✅" if b["status"] == "resolved" else ("🔺" if b["status"] == "escalated" else "🔸")
                with st.expander(f"{sev_color} {b['title']}"):
                    st.write(f"**Severity:** {b['severity'].upper()}  |  **Status:** {status_icon} {b['status']}")
                    st.write(f"**Assigned to:** {b.get('assigned_to','Unassigned')}  |  **Jira:** {b.get('jira_ticket','N/A')}")
                    if b.get("description"):
                        st.write(b["description"])
                    if b.get("ai_suggestion"):
                        st.info(f"✦ AI Suggestion: {b['ai_suggestion']}")
        else:
            st.success("No blockers for this release.")

    with tab_pipeline:
        pipeline = detail.get("pipeline_stages", [])
        if pipeline:
            stages = sorted(pipeline, key=lambda x: x["stage_order"])

            # Draw a visual pipeline
            st.markdown("**CI/CD Pipeline**")
            cols = st.columns(len(stages))
            for i, (col, stage) in enumerate(zip(cols, stages)):
                status_icon = {
                    "success": "✅",
                    "running": "⟳",
                    "failed":  "❌",
                    "pending": "○",
                    "skipped": "⏭",
                }.get(stage["status"], "○")

                with col:
                    st.markdown(f"**{status_icon}**")
                    st.caption(stage["stage_name"])
                    if stage.get("duration_seconds"):
                        st.caption(f"{stage['duration_seconds']}s")
        else:
            st.info("No pipeline data found.")

    with tab_ai:
        st.markdown("**Generate AI Release Notes**")
        audience = st.selectbox(
            "Target audience",
            ["engineering", "product", "merchant", "cab"],
            key=f"audience_{selected_id}"
        )

        # Cache notes in session_state so they don't regenerate on every rerun
        notes_key = f"notes_{selected_id}_{audience}"
        if notes_key not in st.session_state:
            st.session_state[notes_key] = None

        if st.button("✦ Generate Notes", type="primary", key=f"btn_{selected_id}"):
            with st.spinner("AI is writing release notes... (15-30 seconds)"):
                st.session_state[notes_key] = ai_release_notes(selected_id, audience)

        if st.session_state[notes_key]:
            st.markdown(
                f'<div style="background:#0f1117;border:1px solid #00e5a0;border-radius:8px;padding:16px;font-size:14px;line-height:1.7;color:#e2e8f0;">'
                f'{st.session_state[notes_key]}</div>',
                unsafe_allow_html=True
            )
            # Download button — lets you save the notes as a text file
            st.download_button(
                label="⬇ Download Notes",
                data=st.session_state[notes_key],
                file_name=f"{detail['name']}_{detail['version']}_release_notes.txt",
                mime="text/plain"
            )
