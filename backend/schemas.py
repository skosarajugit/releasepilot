# backend/schemas.py
#
# Schemas = the "shape" of data going IN and OUT of the API.
#
# Why do we need schemas if we already have models?
#   - models.py   → defines what's stored in the DATABASE
#   - schemas.py  → defines what the API ACCEPTS and RETURNS
#
# They're often similar but not always the same. For example:
#   - You never want to return 'id' when creating a resource (it doesn't exist yet)
#   - You never want to accept 'created_at' from the user (the server sets that)
#   - You might return extra computed fields not stored in the DB
#
# Pydantic validates data automatically — if a required field is missing
# or the wrong type, FastAPI returns a clear 422 error automatically.

from datetime import datetime
from typing import Optional, List
from pydantic import BaseModel, Field

from backend.models import ReleaseStatus, BlockerSeverity, BlockerStatus, PipelineStageStatus


# ─────────────────────────────────────────────────────────────────────────────
# COMMIT SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class CommitBase(BaseModel):
    """Fields shared between create and read"""
    sha: str
    message: str
    author: str
    jira_ticket: Optional[str] = None
    commit_type: Optional[str] = None   # feat | fix | chore | refactor
    committed_at: Optional[datetime] = None


class CommitCreate(CommitBase):
    """What we accept when creating a commit — release_id comes from the URL"""
    pass


class CommitRead(CommitBase):
    """What we return when reading a commit — includes DB-generated fields"""
    id: int
    release_id: int

    # This tells Pydantic to read data from SQLAlchemy model attributes
    # (not just plain dicts). Without this, release.commits wouldn't work.
    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# BLOCKER SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class BlockerBase(BaseModel):
    title: str
    description: Optional[str] = ""
    severity: BlockerSeverity = BlockerSeverity.MEDIUM
    assigned_to: Optional[str] = None
    jira_ticket: Optional[str] = None


class BlockerCreate(BlockerBase):
    pass


class BlockerUpdate(BaseModel):
    """For PATCH requests — all fields optional so you only send what changed"""
    title: Optional[str] = None
    description: Optional[str] = None
    severity: Optional[BlockerSeverity] = None
    status: Optional[BlockerStatus] = None
    assigned_to: Optional[str] = None
    ai_suggestion: Optional[str] = None
    resolved_at: Optional[datetime] = None


class BlockerRead(BlockerBase):
    id: int
    release_id: int
    status: BlockerStatus
    ai_suggestion: Optional[str] = None
    created_at: datetime
    resolved_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# PIPELINE STAGE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class PipelineStageRead(BaseModel):
    id: int
    release_id: int
    stage_name: str
    stage_order: int
    status: PipelineStageStatus
    duration_seconds: Optional[int] = None
    log_output: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# DEPLOY EVENT SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class DeployEventRead(BaseModel):
    id: int
    release_id: int
    environment: str
    success: bool
    rolled_back: bool
    deployed_at: datetime
    recovered_at: Optional[datetime] = None
    first_commit_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# RELEASE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class ReleaseBase(BaseModel):
    name: str = Field(..., example="POS-Core")
    version: str = Field(..., example="v4.7.2")
    owner: str = Field(..., example="J. Alvarez")
    description: Optional[str] = ""
    target_date: Optional[datetime] = None


class ReleaseCreate(ReleaseBase):
    """What the API accepts when creating a release"""
    pass


class ReleaseUpdate(BaseModel):
    """PATCH — only send what you want to change"""
    name: Optional[str] = None
    version: Optional[str] = None
    owner: Optional[str] = None
    status: Optional[ReleaseStatus] = None
    description: Optional[str] = None
    target_date: Optional[datetime] = None
    deployed_at: Optional[datetime] = None


class ReleaseRead(ReleaseBase):
    """What the API returns — includes everything"""
    id: int
    status: ReleaseStatus
    created_at: datetime
    updated_at: datetime
    deployed_at: Optional[datetime] = None

    model_config = {"from_attributes": True}


class ReleaseReadFull(ReleaseRead):
    """Extended read — includes nested commits, blockers, pipeline stages"""
    commits: List[CommitRead] = []
    blockers: List[BlockerRead] = []
    pipeline_stages: List[PipelineStageRead] = []

    model_config = {"from_attributes": True}


# ─────────────────────────────────────────────────────────────────────────────
# AI REQUEST / RESPONSE SCHEMAS
# ─────────────────────────────────────────────────────────────────────────────

class AIReleaseNotesRequest(BaseModel):
    release_id: int
    audience: str = Field(
        default="engineering",
        description="engineering | product | merchant | cab"
    )


class AITriageRequest(BaseModel):
    blocker_id: int


class AIDoraPlanRequest(BaseModel):
    """Optionally pass current metrics — otherwise the service fetches them"""
    deploy_frequency: Optional[float] = None
    lead_time_hours: Optional[float] = None
    change_failure_rate: Optional[float] = None
    mttr_minutes: Optional[float] = None


class AICABBriefRequest(BaseModel):
    week_label: Optional[str] = None   # e.g. "Week of Apr 21"


class AIResponse(BaseModel):
    """Standard response wrapper for all AI endpoints"""
    result: str
    model_used: str
    release_id: Optional[int] = None
    blocker_id: Optional[int] = None


# ─────────────────────────────────────────────────────────────────────────────
# DORA METRICS SCHEMA
# ─────────────────────────────────────────────────────────────────────────────

class DORAMetrics(BaseModel):
    """The four key DORA metrics"""
    deploy_frequency: float          # Deploys per day (rolling 7-day avg)
    lead_time_hours: float           # Avg hours from first commit to deploy
    change_failure_rate: float       # % of deploys that failed
    mttr_minutes: float              # Avg minutes to recover from a failure
    performance_band: str            # Elite | High | Medium | Low
    total_deploys: int
    period_days: int                 # How many days of data
