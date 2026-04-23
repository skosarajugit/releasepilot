# dashboard/pages/2_Blockers.py
#
# The Blockers page shows all release blockers with AI triage.
# You can filter, view AI suggestions, resolve, and escalate blockers.

import streamlit as st
import sys, os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', '..'))

from dashboard.api_client import (
    get_blockers, resolve_blocker, escalate_blocker, ai_triage_blocker
)

st.set_page_config(page_title="Blockers · ReleasePilot", page_icon="🚧", layout="wide")

st.title("🚧 Release Blockers")
st.caption("AI-powered blocker triage and risk management")
st.divider()

# ── Filters ───────────────────────────────────────────────────────────────────
col_f1, col_f2, col_f3 = st.columns(3)
with col_f1:
    status_filter = st.selectbox("Status", ["open", "escalated", "resolved", "All"])
with col_f2:
    severity_filter = st.selectbox("Severity", ["All", "high", "medium", "low"])
with col_f3:
    st.write("")  # Spacer

status_val   = None if status_filter == "All" else status_filter
severity_val = None if severity_filter == "All" else severity_filter

blockers = get_blockers(status=status_val, severity=severity_val)

# ── Summary stats ─────────────────────────────────────────────────────────────
if blockers:
    all_open     = get_blockers(status="open")
    all_escalated = get_blockers(status="escalated")
    high_open    = get_blockers(status="open", severity="high")

    m1, m2, m3 = st.columns(3)
    m1.metric("Open Blockers",     len(all_open))
    m2.metric("Escalated",         len(all_escalated))
    m3.metric("High Severity Open", len(high_open))
    st.divider()

# ── Blocker list ──────────────────────────────────────────────────────────────
SEV_ICON   = {"high": "🔴", "medium": "🟡", "low": "🔵"}
STATUS_ICON = {"open": "🔸", "resolved": "✅", "escalated": "🔺"}

if not blockers:
    st.success("✅ No blockers match the current filter!")
else:
    st.write(f"Showing **{len(blockers)}** blockers")

    for b in blockers:
        sev    = b.get("severity", "medium")
        status = b.get("status", "open")

        with st.expander(
            f"{SEV_ICON.get(sev,'⚪')} [{sev.upper()}] {b['title']}  "
            f"· {STATUS_ICON.get(status,'○')} {status}  "
            f"· Release #{b['release_id']}"
        ):
            # Details row
            c1, c2, c3 = st.columns(3)
            c1.write(f"**Assigned to:** {b.get('assigned_to','Unassigned')}")
            c2.write(f"**Jira:** {b.get('jira_ticket','N/A')}")
            c3.write(f"**Created:** {b.get('created_at','')[:10]}")

            if b.get("description"):
                st.write(b["description"])

            st.divider()

            # ── AI triage section ─────────────────────────────────────────────
            ai_key = f"triage_{b['id']}"
            if ai_key not in st.session_state:
                # Show cached suggestion from DB if it exists
                st.session_state[ai_key] = b.get("ai_suggestion")

            col_ai, col_resolve, col_escalate = st.columns([2, 1, 1])

            with col_ai:
                if st.button(f"✦ AI Triage", key=f"ai_btn_{b['id']}"):
                    with st.spinner("Analyzing blocker... (15-30 seconds)"):
                        st.session_state[ai_key] = ai_triage_blocker(b["id"])
                    st.rerun()  # Refresh the page to show the result

            with col_resolve:
                if status != "resolved":
                    if st.button("✅ Resolve", key=f"resolve_{b['id']}"):
                        resolve_blocker(b["id"])
                        st.success("Marked as resolved!")
                        st.rerun()

            with col_escalate:
                if status == "open":
                    if st.button("🔺 Escalate", key=f"escalate_{b['id']}"):
                        escalate_blocker(b["id"])
                        st.warning("Escalated!")
                        st.rerun()

            # Show AI suggestion if available
            if st.session_state[ai_key]:
                st.markdown("**✦ AI Triage Suggestion:**")
                st.markdown(
                    f'<div style="background:#0a1a0f;border:1px solid #00e5a0;border-radius:6px;'
                    f'padding:12px;font-size:13px;line-height:1.6;color:#c6f6d5;">'
                    f'{st.session_state[ai_key]}</div>',
                    unsafe_allow_html=True
                )
