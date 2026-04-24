# backend/services/ai_service.py
#
# This is the AI brain of ReleasePilot.
# It wraps Ollama (free, local AI) and provides specific functions
# for each release management task.
#
# How Ollama works:
#   1. You install Ollama on your machine
#   2. You pull a model: `ollama pull llama3`
#   3. You run `ollama serve` to start the local server
#   4. This file sends prompts to http://localhost:11434
#   5. The model generates text and returns it — just like ChatGPT but free
#
# Each function in this file:
#   - Builds a specific prompt with relevant context
#   - Calls Ollama
#   - Returns the generated text

import httpx
from backend.config import settings


# ── Core Ollama caller ────────────────────────────────────────────────────────

async def call_ollama(prompt: str, system: str = None) -> str:
    """
    Send a prompt to Ollama and return the response text.

    Args:
        prompt: The user's question or task
        system: Optional system prompt that sets the AI's persona/behavior

    Returns:
        The AI's response as a string

    Uses httpx (async HTTP client) with a long timeout because
    local AI models can take 30-60 seconds to respond on slower machines.
    """
    # Build the request payload
    # Ollama uses the same format as OpenAI's API — so skills transfer!
    messages = []
    if system:
        messages.append({"role": "system", "content": system})
    messages.append({"role": "user", "content": prompt})

    payload = {
        "model": settings.OLLAMA_MODEL,   # "llama3" from your .env
        "messages": messages,
        "stream": False,                   # Get the full response at once
    }

    try:
        # async with = opens the HTTP client and closes it when done
        # timeout=120 = wait up to 2 minutes (AI can be slow locally)
        async with httpx.AsyncClient(timeout=120) as client:
            response = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/chat",
                json=payload
            )
            response.raise_for_status()   # Raises an error if status != 200
            data = response.json()
            return data["message"]["content"]

    except httpx.ConnectError:
        # Ollama isn't running — return a helpful message instead of crashing
        return (
            "⚠️ Ollama is not running. Start it with: ollama serve\n"
            "Then make sure the model is pulled: ollama pull llama3"
        )
    except Exception as e:
        return f"⚠️ AI service error: {str(e)}"


# ── System prompt ─────────────────────────────────────────────────────────────
# This tells the AI what role to play. Every function below uses this.
SYSTEM_PROMPT = """You are ReleasePilot, an expert AI Release Manager assistant 
for a fintech Point-of-Sale company. You help with:
- Writing clear, professional release documentation
- Triaging release blockers and suggesting fixes
- Analyzing DORA metrics and recommending improvements
- Preparing Change Advisory Board (CAB) meeting briefs

Be concise, technical, and actionable. Write in plain text without markdown 
symbols like ** or ##. Use short paragraphs. Sound like a senior engineer 
who knows the codebase well."""


# ── Task-specific AI functions ────────────────────────────────────────────────

async def generate_release_notes(
    release_name: str,
    version: str,
    commits: list[dict],
    audience: str = "engineering"
) -> str:
    """
    Generate release notes from a list of commits.

    Args:
        release_name: e.g. "POS-Core"
        version: e.g. "v4.7.2"
        commits: list of commit dicts with sha, message, author, type
        audience: engineering | product | merchant | cab
    """
    # Format the commits into a readable list for the prompt
    commit_list = "\n".join([
        f"- [{c.get('type','?')}] {c.get('message','')} ({c.get('author','')})"
        + (f" [{c.get('jira_ticket','')}]" if c.get('jira_ticket') else "")
        for c in commits[:20]   # Cap at 20 commits to keep prompt short
    ])

    # Customize the prompt based on who will read the notes
    audience_instructions = {
        "engineering": "Write for the engineering team. Include technical details, breaking changes, deployment steps, and rollback procedure.",
        "product": "Write for Product Managers and stakeholders. Focus on features and fixes, avoid deep technical details. Highlight merchant impact.",
        "merchant": "Write for external merchants. Use simple language, focus only on visible improvements. Avoid all internal technical details.",
        "cab": "Write a Change Advisory Board summary. Include: change description, risk level, rollback plan, deployment window, and approvals needed.",
    }

    prompt = f"""Generate release notes for {release_name} {version}.

Audience: {audience_instructions.get(audience, audience_instructions['engineering'])}

Commits in this release:
{commit_list}

Structure the notes with these sections:
1. Summary (2-3 sentences)
2. Changes (grouped by type: Features, Bug Fixes, Improvements)
3. Deployment Notes
4. Rollback Procedure
"""
    return await call_ollama(prompt, SYSTEM_PROMPT)


async def triage_blocker(
    title: str,
    description: str,
    severity: str,
    release_name: str
) -> str:
    """
    Analyze a release blocker and suggest a resolution.

    Args:
        title: Blocker title
        description: Detailed description
        severity: low | medium | high
        release_name: Which release this blocks
    """
    prompt = f"""Triage this release blocker for {release_name}:

Title: {title}
Severity: {severity}
Description: {description}

Provide:
1. Root cause analysis (1-2 sentences)
2. Recommended immediate action (specific, actionable)
3. Suggested owner/team to fix this
4. Estimated resolution time
5. Risk if not resolved before release
"""
    return await call_ollama(prompt, SYSTEM_PROMPT)


async def generate_dora_plan(
    deploy_frequency: float,
    lead_time_hours: float,
    change_failure_rate: float,
    mttr_minutes: float,
    performance_band: str
) -> str:
    """
    Generate an improvement plan based on current DORA metrics.
    """
    prompt = f"""Analyze these DORA metrics and create an improvement roadmap:

Current Metrics:
- Deploy Frequency: {deploy_frequency:.1f} deploys/day
- Lead Time for Changes: {lead_time_hours:.1f} hours
- Change Failure Rate: {change_failure_rate:.1f}%
- Mean Time to Recovery (MTTR): {mttr_minutes:.0f} minutes
- Overall Performance Band: {performance_band}

DORA Elite thresholds for reference:
- Deploy Frequency: multiple times per day
- Lead Time: less than 1 hour
- Change Failure Rate: 0-5%
- MTTR: less than 1 hour

Provide a 3-point improvement plan. For each point:
- What to improve
- Specific action to take
- Expected impact on which metric
- Timeframe to see results
"""
    return await call_ollama(prompt, SYSTEM_PROMPT)


async def generate_cab_brief(
    change_requests: list[dict],
    week_label: str = "This Week"
) -> str:
    """
    Generate a Change Advisory Board meeting brief.

    Args:
        change_requests: list of dicts with title, risk, status, requester
        week_label: e.g. "Week of Apr 21"
    """
    cr_list = "\n".join([
        f"- {cr.get('title','')} | Risk: {cr.get('risk','unknown')} | "
        f"Requester: {cr.get('requester','')} | Status: {cr.get('status','')}"
        for cr in change_requests
    ])

    prompt = f"""Prepare a Change Advisory Board (CAB) brief for {week_label}.

Change Requests:
{cr_list}

Write a professional CAB brief that includes:
1. Meeting overview (1 paragraph)
2. For each change request: recommendation (Approve / Hold / Reject) with brief justification
3. Risk summary across all changes
4. Suggested agenda order (highest risk items first)
5. Any dependencies or conflicts between changes
"""
    return await call_ollama(prompt, SYSTEM_PROMPT)


async def generate_sprint_summary(releases: list[dict]) -> str:
    """
    Generate a high-level sprint health summary for the dashboard.

    Args:
        releases: list of release dicts with name, version, status, blocker_count
    """
    release_list = "\n".join([
        f"- {r.get('name','')} {r.get('version','')} | Status: {r.get('status','')} "
        f"| Blockers: {r.get('blocker_count', 0)}"
        for r in releases
    ])

    prompt = f"""Give a concise sprint health summary for a Release Manager:

Active Releases:
{release_list}

Provide:
1. Overall sprint health (1 sentence)
2. Top 2 risks to address today
3. One recommended action for the release manager right now
Keep it under 100 words total.
"""
    return await call_ollama(prompt, SYSTEM_PROMPT)
