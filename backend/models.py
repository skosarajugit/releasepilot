# backend/models.py
#
# Models = database tables, written as Python classes.
#
# Each class = one table.
# Each class attribute with Column() = one column in that table.
#
# SQLAlchemy reads these classes and creates the actual SQL tables for you.
# You never have to write CREATE TABLE statements manually.

from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Text, Float,
    DateTime, ForeignKey, Enum, Boolean
)
from sqlalchemy.orm import relationship
import enum

from backend.database import Base


# ── Enums ─────────────────────────────────────────────────────────────────────
# Enums restrict a column to a fixed set of values.
# This prevents typos like "in progres" or "RUNNING" vs "running".

class ReleaseStatus(str, enum.Enum):
    PLANNING    = "planning"
    IN_PROGRESS = "in_progress"
    QA_REVIEW   = "qa_review"
    CAB_PENDING = "cab_pending"
    APPROVED    = "approved"
    DEPLOYED    = "deployed"
    ROLLED_BACK = "rolled_back"


class BlockerSeverity(str, enum.Enum):
    LOW    = "low"
    MEDIUM = "medium"
    HIGH   = "high"


class BlockerStatus(str, enum.Enum):
    OPEN     = "open"
    RESOLVED = "resolved"
    ESCALATED = "escalated"


class PipelineStageStatus(str, enum.Enum):
    PENDING  = "pending"
    RUNNING  = "running"
    SUCCESS  = "success"
    FAILED   = "failed"
    SKIPPED  = "skipped"


# ── Release Model ─────────────────────────────────────────────────────────────
class Release(Base):
    """
    Represents a software release (e.g., POS-Core v4.7.2).

    One release has:
      - many commits    (one-to-many)
      - many blockers   (one-to-many)
      - many pipeline stages (one-to-many)
      - many deploy events  (one-to-many)
    """
    __tablename__ = "releases"

    id          = Column(Integer, primary_key=True, index=True)
    name        = Column(String(100), nullable=False)        # e.g. "POS-Core"
    version     = Column(String(50),  nullable=False)        # e.g. "v4.7.2"
    owner       = Column(String(100), nullable=False)        # e.g. "J. Alvarez"
    status      = Column(Enum(ReleaseStatus), default=ReleaseStatus.PLANNING)
    target_date = Column(DateTime, nullable=True)
    deployed_at = Column(DateTime, nullable=True)            # Set when deployed
    description = Column(Text, default="")

    # Timestamps — set automatically
    created_at  = Column(DateTime, default=datetime.utcnow)
    updated_at  = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships — these let you do release.commits to get all commits
    # back_populates="release" means the Commit model also has a .release attribute
    commits         = relationship("Commit",         back_populates="release", cascade="all, delete")
    blockers        = relationship("Blocker",        back_populates="release", cascade="all, delete")
    pipeline_stages = relationship("PipelineStage",  back_populates="release", cascade="all, delete")
    deploy_events   = relationship("DeployEvent",    back_populates="release", cascade="all, delete")

    def __repr__(self):
        return f"<Release {self.name} {self.version} [{self.status}]>"


# ── Commit Model ──────────────────────────────────────────────────────────────
class Commit(Base):
    """
    Represents a git commit linked to a release.
    These are used to generate AI release notes.
    """
    __tablename__ = "commits"

    id          = Column(Integer, primary_key=True, index=True)
    release_id  = Column(Integer, ForeignKey("releases.id"), nullable=False)

    sha         = Column(String(40),  nullable=False)        # Git SHA e.g. "a3f7c92"
    message     = Column(Text,        nullable=False)        # Commit message
    author      = Column(String(100), nullable=False)        # Author name
    jira_ticket = Column(String(50),  nullable=True)         # e.g. "CLOVER-4821"
    commit_type = Column(String(20),  nullable=True)         # feat|fix|chore|refactor
    committed_at = Column(DateTime,   default=datetime.utcnow)

    # Foreign key relationship back to Release
    release = relationship("Release", back_populates="commits")

    def __repr__(self):
        return f"<Commit {self.sha[:7]} {self.message[:40]}>"


# ── Blocker Model ─────────────────────────────────────────────────────────────
class Blocker(Base):
    """
    Represents a release blocker or risk item.
    These are triaged by the AI service.
    """
    __tablename__ = "blockers"

    id          = Column(Integer, primary_key=True, index=True)
    release_id  = Column(Integer, ForeignKey("releases.id"), nullable=False)

    title       = Column(String(200), nullable=False)
    description = Column(Text,        default="")
    severity    = Column(Enum(BlockerSeverity), default=BlockerSeverity.MEDIUM)
    status      = Column(Enum(BlockerStatus),   default=BlockerStatus.OPEN)
    assigned_to = Column(String(100), nullable=True)
    jira_ticket = Column(String(50),  nullable=True)

    # AI-generated triage suggestion (stored so we don't re-call AI every time)
    ai_suggestion = Column(Text, nullable=True)

    created_at  = Column(DateTime, default=datetime.utcnow)
    resolved_at = Column(DateTime, nullable=True)

    release = relationship("Release", back_populates="blockers")

    def __repr__(self):
        return f"<Blocker [{self.severity}] {self.title[:50]}>"


# ── PipelineStage Model ───────────────────────────────────────────────────────
class PipelineStage(Base):
    """
    Represents one stage in a CI/CD pipeline run.
    e.g. SCM Checkout → Build → Unit Tests → Integration → QA Gate → Deploy
    """
    __tablename__ = "pipeline_stages"

    id          = Column(Integer, primary_key=True, index=True)
    release_id  = Column(Integer, ForeignKey("releases.id"), nullable=False)

    stage_name  = Column(String(100), nullable=False)         # e.g. "Unit Tests"
    stage_order = Column(Integer,     nullable=False)         # 1, 2, 3... (display order)
    status      = Column(Enum(PipelineStageStatus), default=PipelineStageStatus.PENDING)
    duration_seconds = Column(Integer, nullable=True)         # How long the stage took
    log_output  = Column(Text, nullable=True)                 # Last few lines of logs
    started_at  = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)

    release = relationship("Release", back_populates="pipeline_stages")

    def __repr__(self):
        return f"<PipelineStage {self.stage_name} [{self.status}]>"


# ── DeployEvent Model ─────────────────────────────────────────────────────────
class DeployEvent(Base):
    """
    Records every deployment attempt for a release.
    Used by Pandas to calculate DORA metrics:
      - Deploy Frequency   → count events per day
      - Change Failure Rate → count failed / total
      - MTTR               → time from failed to recovered
      - Lead Time          → commit timestamp to deploy timestamp
    """
    __tablename__ = "deploy_events"

    id          = Column(Integer, primary_key=True, index=True)
    release_id  = Column(Integer, ForeignKey("releases.id"), nullable=False)

    environment = Column(String(50),  default="production")   # staging|production
    success     = Column(Boolean,     default=True)           # Did the deploy succeed?
    rolled_back = Column(Boolean,     default=False)          # Was it rolled back?

    # For MTTR calculation: if a deploy failed, when was it recovered?
    recovered_at = Column(DateTime, nullable=True)

    # For Lead Time: when was the first commit in this release made?
    first_commit_at = Column(DateTime, nullable=True)

    deployed_at = Column(DateTime, default=datetime.utcnow)

    release = relationship("Release", back_populates="deploy_events")

    def __repr__(self):
        status = "✓" if self.success else "✗"
        return f"<DeployEvent {status} {self.release_id} @ {self.deployed_at}>"
