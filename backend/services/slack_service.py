# backend/services/slack_service.py
#
# This service sends notifications to Slack (or simulates them).
#
# How Slack webhooks work:
#   1. You create an "Incoming Webhook" in Slack settings
#   2. Slack gives you a URL like https://hooks.slack.com/services/XXX/YYY/ZZZ
#   3. You POST a JSON payload to that URL
#   4. Slack displays the message in your chosen channel
#
# If SLACK_WEBHOOK_URL is empty in .env, we just log the payload to console.
# This way the code works in demo mode without needing a real Slack workspace.
#
# Slack message format uses "Block Kit" — a JSON structure for rich messages.
# Learn more: https://app.slack.com/block-kit-builder

import httpx
import json
from datetime import datetime
from backend.config import settings


# ── Core sender ───────────────────────────────────────────────────────────────

async def send_slack_message(blocks: list, text: str = "ReleasePilot Notification") -> bool:
    """
    Send a formatted message to Slack.

    Args:
        blocks: Slack Block Kit blocks (rich formatting)
        text:   Fallback plain text (shown in notifications)

    Returns:
        True if sent successfully, False otherwise.

    If no webhook URL is configured, pretty-prints to console instead.
    """
    payload = {"text": text, "blocks": blocks}

    # ── No webhook configured — log to console ───────────────────────────────
    if not settings.SLACK_WEBHOOK_URL:
        print("\n" + "="*60)
        print("📣 SLACK NOTIFICATION (simulated — no webhook configured)")
        print("="*60)
        print(f"Text: {text}")
        print("Blocks:")
        print(json.dumps(blocks, indent=2))
        print("="*60 + "\n")
        return True  # Return True so callers know it "worked"

    # ── Real webhook — POST to Slack ──────────────────────────────────────────
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            response = await client.post(
                settings.SLACK_WEBHOOK_URL,
                json=payload
            )
            # Slack returns "ok" as plain text on success
            if response.text == "ok":
                print(f"✅ Slack notification sent: {text}")
                return True
            else:
                print(f"⚠️  Slack returned unexpected response: {response.text}")
                return False

    except httpx.ConnectError:
        print("⚠️  Could not reach Slack webhook URL")
        return False
    except Exception as e:
        print(f"⚠️  Slack error: {str(e)}")
        return False


# ── Notification templates ────────────────────────────────────────────────────
# Each function below builds a specific Slack message type using Block Kit.
# Block Kit uses a list of "blocks" — each block is a section of the message.
# Types used here:
#   header  → large title bar
#   section → text content, supports markdown with *bold* and `code`
#   divider → horizontal line
#   context → small grey footer text

async def notify_deploy_started(release_name: str, version: str, environment: str, owner: str):
    """
    Notification sent when a deployment begins.
    Example: "🚀 POS-Core v4.7.2 deploying to production"
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🚀 Deploy Started — {release_name} {version}"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Release:*\n`{release_name} {version}`"},
                {"type": "mrkdwn", "text": f"*Environment:*\n{environment.upper()}"},
                {"type": "mrkdwn", "text": f"*Owner:*\n{owner}"},
                {"type": "mrkdwn", "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [
                {"type": "mrkdwn", "text": "ReleasePilot · Monitor at http://localhost:8501"}
            ]
        }
    ]
    await send_slack_message(
        blocks,
        text=f"🚀 Deploy started: {release_name} {version} → {environment}"
    )


async def notify_deploy_success(release_name: str, version: str, environment: str, duration_minutes: float = None):
    """
    Notification sent when a deployment completes successfully.
    """
    duration_text = f"{duration_minutes:.1f} min" if duration_minutes else "unknown"

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"✅ Deploy Successful — {release_name} {version}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*{release_name} {version}* has been successfully deployed to *{environment.upper()}*."
            }
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Duration:*\n{duration_text}"},
                {"type": "mrkdwn", "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            ]
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "ReleasePilot · All systems go 🟢"}]
        }
    ]
    await send_slack_message(
        blocks,
        text=f"✅ Deploy successful: {release_name} {version} → {environment}"
    )


async def notify_deploy_failed(release_name: str, version: str, environment: str, reason: str = None):
    """
    Notification sent when a deployment fails.
    Marked as urgent — uses a red-coded message.
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"❌ Deploy FAILED — {release_name} {version}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{release_name} {version}* deployment to *{environment.upper()}* has failed.\n"
                    f"Immediate action required — check rollback procedure."
                )
            }
        },
    ]

    if reason:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Failure reason:*\n```{reason}```"}
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": "*Action Required:*\n• Assess rollback\n• Page on-call engineer\n• Open incident ticket"},
                {"type": "mrkdwn", "text": f"*Time:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            ]
        },
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "ReleasePilot · 🔴 Incident response needed"}]
        }
    ]
    await send_slack_message(
        blocks,
        text=f"❌ DEPLOY FAILED: {release_name} {version} → {environment}"
    )


async def notify_blocker_flagged(
    blocker_title: str,
    release_name: str,
    severity: str,
    assigned_to: str = None,
    ai_suggestion: str = None
):
    """
    Notification sent when a new high/medium severity blocker is created.
    Includes AI triage suggestion if available.
    """
    # Color-code by severity using Slack's emoji system
    sev_config = {
        "high":   ("🔴", "CRITICAL BLOCKER"),
        "medium": ("🟡", "Release Blocker"),
        "low":    ("🔵", "Minor Blocker"),
    }
    icon, label = sev_config.get(severity, ("⚪", "Blocker"))

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"{icon} {label} Flagged — {release_name}"}
        },
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*{blocker_title}*"}
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Release:*\n{release_name}"},
                {"type": "mrkdwn", "text": f"*Severity:*\n{severity.upper()}"},
                {"type": "mrkdwn", "text": f"*Assigned to:*\n{assigned_to or 'Unassigned'}"},
                {"type": "mrkdwn", "text": f"*Flagged at:*\n{datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}"},
            ]
        },
    ]

    # Add AI suggestion if provided
    if ai_suggestion:
        # Truncate long AI text for Slack (max 3000 chars per block)
        short_suggestion = ai_suggestion[:400] + "..." if len(ai_suggestion) > 400 else ai_suggestion
        blocks.append({
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*✦ AI Triage Suggestion:*\n{short_suggestion}"
            }
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "ReleasePilot · View full details at http://localhost:8501"}]
        }
    ]
    await send_slack_message(
        blocks,
        text=f"{icon} Blocker flagged for {release_name}: {blocker_title}"
    )


async def notify_cab_approved(release_name: str, version: str, deploy_window: str = None):
    """
    Notification sent when a release is approved by CAB.
    """
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"✅ CAB Approved — {release_name} {version}"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": (
                    f"*{release_name} {version}* has been approved by the Change Advisory Board "
                    f"and is cleared for production deployment."
                )
            }
        },
    ]

    if deploy_window:
        blocks.append({
            "type": "section",
            "text": {"type": "mrkdwn", "text": f"*Deployment Window:*\n{deploy_window}"}
        })

    blocks += [
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "ReleasePilot · CAB approval recorded 🟢"}]
        }
    ]
    await send_slack_message(
        blocks,
        text=f"✅ CAB approved: {release_name} {version}"
    )


async def notify_release_summary(releases_summary: list):
    """
    Daily/weekly digest of all release statuses.
    Good for end-of-day Slack standup summaries.
    """
    STATUS_EMOJI = {
        "deployed":    "🟢",
        "in_progress": "🟡",
        "qa_review":   "🔵",
        "planning":    "⚪",
        "cab_pending": "🟠",
        "rolled_back": "🔴",
    }

    release_lines = "\n".join([
        f"{STATUS_EMOJI.get(r.get('status',''), '⚪')} *{r['name']} {r['version']}* — "
        f"{r['status'].replace('_',' ').title()} · {r.get('owner','')}"
        for r in releases_summary
    ])

    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": "📦 ReleasePilot Daily Digest"}
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Release Status Summary — {datetime.utcnow().strftime('%b %d, %Y')}*\n\n{release_lines}"
            }
        },
        {"type": "divider"},
        {
            "type": "context",
            "elements": [{"type": "mrkdwn", "text": "ReleasePilot · http://localhost:8501"}]
        }
    ]
    await send_slack_message(blocks, text="📦 ReleasePilot Daily Digest")
