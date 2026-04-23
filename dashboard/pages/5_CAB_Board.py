# dashboard/pages/5_CAB_Board.py
#
# Change Advisory Board page.
# Shows all active releases pending CAB review and generates
# an AI-written meeting brief.

import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.api_client import get_releases, ai_cab_brief

st.set_page_config(page_title="CAB Board · ReleasePilot", page_icon="📋", layout="wide")

st.title("📋 Change Advisory Board")
st.caption("Weekly CAB meeting management and AI-generated briefings")
st.divider()

# ── Change requests table ─────────────────────────────────────────────────────
st.subheader("Active Change Requests")

releases = get_releases()
active   = [r for r in releases if r["status"] not in ("deployed", "rolled_back")]

if not active:
    st.success("No pending change requests this week.")
else:
    import pandas as pd

    RISK_MAP = {
        "planning":    ("Low",    "🔵"),
        "in_progress": ("Medium", "🟡"),
        "qa_review":   ("Medium", "🟡"),
        "cab_pending": ("High",   "🔴"),
        "approved":    ("Low",    "🟢"),
    }

    rows = []
    for r in active:
        risk_label, risk_icon = RISK_MAP.get(r["status"], ("Unknown","⚪"))
        rows.append({
            "Change Request": f"{r['name']} {r['version']}",
            "Owner":          r["owner"],
            "Risk":           f"{risk_icon} {risk_label}",
            "Status":         r["status"].replace("_"," ").title(),
            "Target Date":    r.get("target_date","")[:10] if r.get("target_date") else "TBD",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

st.divider()

# ── CAB Brief Generator ───────────────────────────────────────────────────────
st.subheader("✦ AI CAB Meeting Brief")
st.caption("Generates a professional Change Advisory Board brief ready for your Thursday meeting")

week_label = st.text_input("Week label (optional)", placeholder="e.g. Week of Apr 28")

brief_key = "cab_brief"
if brief_key not in st.session_state:
    st.session_state[brief_key] = None

if st.button("✦ Generate CAB Brief", type="primary"):
    with st.spinner("AI is preparing the CAB brief... (15-30 seconds)"):
        st.session_state[brief_key] = ai_cab_brief(week_label or None)

if st.session_state[brief_key]:
    st.markdown(
        f'<div style="background:#0f1117;border:1px solid #00e5a0;border-radius:8px;'
        f'padding:20px;font-size:14px;line-height:1.8;color:#e2e8f0;">'
        f'{st.session_state[brief_key]}</div>',
        unsafe_allow_html=True
    )
    st.download_button(
        label="⬇ Download CAB Brief",
        data=st.session_state[brief_key],
        file_name="cab_brief.txt",
        mime="text/plain"
    )

st.divider()

# ── CAB Tips ──────────────────────────────────────────────────────────────────
with st.expander("💡 CAB Best Practices"):
    st.markdown("""
**Before the meeting:**
- Ensure all high-risk changes have rollback plans documented
- Confirm QA sign-off is complete for items going to Approve
- Check for scheduling conflicts between related deployments

**During the meeting:**
- Review highest-risk items first
- Verify deployment windows don't overlap
- Confirm on-call engineers are scheduled for each deployment

**Change Risk Criteria:**
- **High**: DB migrations, auth changes, payment processing, >5 services affected
- **Medium**: API changes, UI updates, config changes in production
- **Low**: Documentation, minor bug fixes, internal tooling
    """)
