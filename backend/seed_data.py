# backend/seed_data.py
#
# This script populates the database with realistic demo data.
# Run it once after setting up the database:
#   python -m backend.seed_data
#
# It uses the Faker library to generate realistic names, dates, and text.


from datetime import datetime, timedelta
import random
from faker import Faker

from backend.database import SessionLocal, create_tables
from backend.models import (
    Release, Commit, Blocker, PipelineStage, DeployEvent,
    ReleaseStatus, BlockerSeverity, BlockerStatus, PipelineStageStatus
)

fake = Faker()
random.seed(42)  # Fixed seed = same data every time you run this


# ── Constants ─────────────────────────────────────────────────────────────────

SERVICES = [
    ("POS-Core",        "v4.7.2", "J. Alvarez",  ReleaseStatus.IN_PROGRESS),
    ("Payments-API",    "v2.1.0", "M. Chen",      ReleaseStatus.QA_REVIEW),
    ("Merchant-Portal", "v1.9.1", "S. Okafor",    ReleaseStatus.PLANNING),
    ("Inventory-Svc",   "v3.0.0", "A. Patel",     ReleaseStatus.DEPLOYED),
    ("Auth-Service",    "v1.4.5", "K. Williams",  ReleaseStatus.DEPLOYED),
    ("Analytics-API",   "v2.3.1", "R. Singh",     ReleaseStatus.DEPLOYED),
]

# Realistic commit message patterns (conventional commits format)
COMMIT_TEMPLATES = [
    ("feat",     "feat({scope}): add {feature}"),
    ("fix",      "fix({scope}): resolve {issue}"),
    ("refactor", "refactor({scope}): {action} for {reason}"),
    ("chore",    "chore({scope}): {action}"),
    ("test",     "test({scope}): add coverage for {feature}"),
    ("docs",     "docs({scope}): update {doc_type} documentation"),
]

SCOPES = ["payments", "db", "api", "auth", "cache", "ui", "ci", "config", "logging"]

FEATURES = [
    "idempotency key support for transaction retries",
    "real-time inventory sync webhook",
    "multi-currency support for merchant dashboard",
    "rate limiting on public API endpoints",
    "bulk refund processing endpoint",
    "merchant category code (MCC) validation",
]

ISSUES = [
    "race condition in settlement batch processor",
    "null pointer in tax calculation for split payments",
    "memory leak in long-running WebSocket connections",
    "incorrect rounding in currency conversion",
    "session timeout not enforced on mobile SDK",
]

PIPELINE_STAGES = [
    ("SCM Checkout",  1),
    ("Build",         2),
    ("Unit Tests",    3),
    ("Integration Tests", 4),
    ("QA Gate",       5),
    ("Deploy Staging", 6),
    ("Smoke Tests",   7),
    ("Deploy Prod",   8),
]

BLOCKER_TEMPLATES = [
    ("DB schema migration — no rollback plan defined",   BlockerSeverity.HIGH),
    ("QA sign-off delayed — missing test coverage",      BlockerSeverity.MEDIUM),
    ("TLS certificate expiry approaching",               BlockerSeverity.LOW),
    ("Breaking API change not communicated to consumers", BlockerSeverity.HIGH),
    ("Jenkins pipeline flaky — intermittent failures",   BlockerSeverity.MEDIUM),
    ("Dependency CVE vulnerability unfixed",             BlockerSeverity.HIGH),
    ("Config drift between staging and production",      BlockerSeverity.MEDIUM),
    ("Performance regression in P95 latency",           BlockerSeverity.MEDIUM),
]


# ── Helper functions ──────────────────────────────────────────────────────────

def random_date(days_ago_min=1, days_ago_max=30):
    """Returns a random datetime between days_ago_min and days_ago_max days ago"""
    delta = random.randint(days_ago_min, days_ago_max)
    return datetime.utcnow() - timedelta(days=delta, hours=random.randint(0, 23))


def make_sha():
    """Generate a fake git SHA (7 chars for display, 40 for storage)"""
    return fake.sha1()[:40]


def make_commit_message():
    """Generate a realistic conventional commit message"""
    commit_type, template = random.choice(COMMIT_TEMPLATES)
    scope = random.choice(SCOPES)
    msg = template.format(
        scope=scope,
        feature=random.choice(FEATURES),
        issue=random.choice(ISSUES),
        action=random.choice(["migrate", "refactor", "update", "clean up", "optimize"]),
        reason=random.choice(["performance", "maintainability", "scalability"]),
        doc_type=random.choice(["API", "README", "deployment", "runbook"]),
    )
    return commit_type, msg


def make_jira_ticket():
    """Generate a fake Jira ticket number"""
    return f"PROJ-{random.randint(4500, 5000)}"


# ── Seed functions ────────────────────────────────────────────────────────────

def seed_releases(db) -> list[Release]:
    """Create the main releases"""
    print("  Creating releases...")
    releases = []
    for name, version, owner, status in SERVICES:
        days_out = random.randint(3, 20)
        target = datetime.utcnow() + timedelta(days=days_out)
        deployed_at = None

        if status == ReleaseStatus.DEPLOYED:
            deployed_at = random_date(1, 14)
            target = deployed_at

        release = Release(
            name=name,
            version=version,
            owner=owner,
            status=status,
            target_date=target,
            deployed_at=deployed_at,
            description=f"{name} release {version} — automated via ReleasePilot AI",
        )
        db.add(release)
        releases.append(release)

    db.flush()  # Flush to get IDs without committing yet
    return releases


def seed_commits(db, releases: list[Release]):
    """Add realistic commits to each release"""
    print("  Creating commits...")
    for release in releases:
        num_commits = random.randint(4, 12)
        for i in range(num_commits):
            commit_type, message = make_commit_message()
            commit = Commit(
                release_id=release.id,
                sha=make_sha(),
                message=message,
                author=random.choice(["J. Alvarez", "M. Chen", "S. Okafor", "A. Patel", "K. Williams", "R. Singh"]),
                jira_ticket=make_jira_ticket() if random.random() > 0.2 else None,
                commit_type=commit_type,
                committed_at=random_date(1, 20),
            )
            db.add(commit)


def seed_pipeline_stages(db, releases: list[Release]):
    """Add CI/CD pipeline stages to each release"""
    print("  Creating pipeline stages...")
    for release in releases:
        if release.status == ReleaseStatus.DEPLOYED:
            # Fully completed pipeline
            statuses = [PipelineStageStatus.SUCCESS] * len(PIPELINE_STAGES)
        elif release.status == ReleaseStatus.IN_PROGRESS:
            # Partially completed — first 3 done, one running, rest pending
            statuses = (
                [PipelineStageStatus.SUCCESS] * 3 +
                [PipelineStageStatus.RUNNING] +
                [PipelineStageStatus.PENDING] * (len(PIPELINE_STAGES) - 4)
            )
        elif release.status == ReleaseStatus.QA_REVIEW:
            # Build done, in QA
            statuses = (
                [PipelineStageStatus.SUCCESS] * 5 +
                [PipelineStageStatus.RUNNING] +
                [PipelineStageStatus.PENDING] * 2
            )
        else:
            # Planning — nothing started
            statuses = [PipelineStageStatus.PENDING] * len(PIPELINE_STAGES)

        for (stage_name, order), status in zip(PIPELINE_STAGES, statuses):
            stage = PipelineStage(
                release_id=release.id,
                stage_name=stage_name,
                stage_order=order,
                status=status,
                duration_seconds=random.randint(10, 300) if status == PipelineStageStatus.SUCCESS else None,
                started_at=random_date(0, 3) if status != PipelineStageStatus.PENDING else None,
                finished_at=random_date(0, 2) if status == PipelineStageStatus.SUCCESS else None,
            )
            db.add(stage)


def seed_blockers(db, releases: list[Release]):
    """Add release blockers to active releases"""
    print("  Creating blockers...")
    active_releases = [r for r in releases if r.status != ReleaseStatus.DEPLOYED]

    for release in active_releases:
        num_blockers = random.randint(1, 3)
        selected = random.sample(BLOCKER_TEMPLATES, min(num_blockers, len(BLOCKER_TEMPLATES)))

        for title, severity in selected:
            status = random.choice([BlockerStatus.OPEN, BlockerStatus.OPEN, BlockerStatus.ESCALATED])
            blocker = Blocker(
                release_id=release.id,
                title=title,
                description=f"Identified during sprint planning for {release.name} {release.version}.",
                severity=severity,
                status=status,
                assigned_to=random.choice(["J. Alvarez", "M. Chen", "K. Williams", "QA Team"]),
                jira_ticket=make_jira_ticket(),
            )
            db.add(blocker)


def seed_deploy_events(db, releases: list[Release]):
    """
    Create historical deploy events for DORA metrics calculation.
    We generate 90 days of deploy history so Pandas has enough data for trends.
    """
    print("  Creating deploy events (90 days of history)...")

    # For deployed releases, add their actual deploy event
    for release in releases:
        if release.status == ReleaseStatus.DEPLOYED and release.deployed_at:
            first_commit = release.deployed_at - timedelta(hours=random.randint(1, 48))
            event = DeployEvent(
                release_id=release.id,
                environment="production",
                success=True,
                rolled_back=False,
                deployed_at=release.deployed_at,
                first_commit_at=first_commit,
            )
            db.add(event)

    # Generate additional synthetic historical events for DORA trend data
    # We'll use the first deployed release as an anchor
    deployed_releases = [r for r in releases if r.status == ReleaseStatus.DEPLOYED]
    if not deployed_releases:
        return

    anchor_release = deployed_releases[0]

    for day in range(90):
        # Simulate 3-6 deploys per day (Elite DORA tier)
        num_deploys = random.randint(2, 6)
        base_date = datetime.utcnow() - timedelta(days=day)

        for _ in range(num_deploys):
            deploy_time = base_date.replace(
                hour=random.randint(8, 18),
                minute=random.randint(0, 59)
            )
            # 95% success rate (realistic for a good team)
            success = random.random() > 0.05
            recovered_at = None

            if not success:
                # MTTR: recover within 15-90 minutes
                recovered_at = deploy_time + timedelta(minutes=random.randint(15, 90))

            event = DeployEvent(
                release_id=anchor_release.id,
                environment="production",
                success=success,
                rolled_back=not success and random.random() > 0.5,
                deployed_at=deploy_time,
                recovered_at=recovered_at,
                # Lead time: 1-48 hours from commit to deploy
                first_commit_at=deploy_time - timedelta(hours=random.randint(1, 48)),
            )
            db.add(event)


# ── Main entry point ──────────────────────────────────────────────────────────

def run_seed():
    print("🌱 Seeding ReleasePilot database...")

    # Create all tables first
    create_tables()

    db = SessionLocal()
    try:
        # Check if already seeded
        existing = db.query(Release).count()
        if existing > 0:
            print(f"  Database already has {existing} releases. Skipping seed.")
            print("  To re-seed, delete releasepilot.db and run again.")
            return

        releases = seed_releases(db)
        seed_commits(db, releases)
        seed_pipeline_stages(db, releases)
        seed_blockers(db, releases)
        seed_deploy_events(db, releases)

        # Commit everything in one transaction
        db.commit()
        print(f"\n✅ Seeded successfully!")
        print(f"   {len(releases)} releases")
        print(f"   Check releasepilot.db with: sqlite3 releasepilot.db '.tables'")

    except Exception as e:
        db.rollback()
        print(f"❌ Seed failed: {e}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    run_seed()
