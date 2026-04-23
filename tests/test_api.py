# tests/test_api.py
#
# Basic tests for the FastAPI backend.
#
# pytest finds any file starting with test_ and runs functions starting with test_.
# We use FastAPI's TestClient — it simulates HTTP requests without needing
# a real running server.
#
# Run tests with:
#   pytest tests/ -v

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.main import app
from backend.database import Base, get_db

# ── Test database setup ───────────────────────────────────────────────────────
# We use a separate in-memory SQLite database for tests.
# This means tests don't affect your real releasepilot.db file.
TEST_DATABASE_URL = "sqlite:///./test_releasepilot.db"

engine = create_engine(TEST_DATABASE_URL, connect_args={"check_same_thread": False})
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def override_get_db():
    """Replace the real DB session with a test DB session"""
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()


# Override the dependency — all requests during tests use the test DB
app.dependency_overrides[get_db] = override_get_db

# Create all tables in the test DB
Base.metadata.create_all(bind=engine)

# TestClient wraps the FastAPI app — lets us make requests without a server
client = TestClient(app)


# ── Tests ─────────────────────────────────────────────────────────────────────

def test_health_check():
    """The /health endpoint should always return 200"""
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_root():
    """Root endpoint returns welcome message"""
    response = client.get("/")
    assert response.status_code == 200
    assert "ReleasePilot" in response.json()["message"]


def test_get_releases_empty():
    """Releases endpoint returns empty list when DB is empty"""
    response = client.get("/releases/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_create_release():
    """Creating a release returns 201 with the created data"""
    payload = {
        "name": "Test-Service",
        "version": "v1.0.0",
        "owner": "Test User",
        "description": "Test release"
    }
    response = client.post("/releases/", json=payload)
    assert response.status_code == 201

    data = response.json()
    assert data["name"] == "Test-Service"
    assert data["version"] == "v1.0.0"
    assert data["status"] == "planning"     # Default status
    assert "id" in data                     # DB assigned an ID
    assert "created_at" in data             # Timestamp was set

    return data["id"]   # Return ID for use in other tests


def test_get_release_by_id():
    """Can fetch a specific release by ID"""
    # First create one
    create_response = client.post("/releases/", json={
        "name": "FetchTest",
        "version": "v2.0.0",
        "owner": "Test Owner"
    })
    release_id = create_response.json()["id"]

    # Now fetch it
    response = client.get(f"/releases/{release_id}")
    assert response.status_code == 200
    assert response.json()["id"] == release_id
    assert response.json()["name"] == "FetchTest"


def test_get_release_not_found():
    """Fetching a non-existent release returns 404"""
    response = client.get("/releases/99999")
    assert response.status_code == 404


def test_update_release_status():
    """Can update a release's status with PATCH"""
    # Create a release
    create_response = client.post("/releases/", json={
        "name": "PatchTest",
        "version": "v3.0.0",
        "owner": "Test Owner"
    })
    release_id = create_response.json()["id"]

    # Update the status
    response = client.patch(f"/releases/{release_id}", json={"status": "in_progress"})
    assert response.status_code == 200
    assert response.json()["status"] == "in_progress"

    # Other fields should be unchanged
    assert response.json()["name"] == "PatchTest"


def test_create_blocker():
    """Can create a blocker for a release"""
    # Create a release first
    release = client.post("/releases/", json={
        "name": "BlockerTest",
        "version": "v1.0.0",
        "owner": "Test"
    }).json()

    # Create a blocker
    response = client.post(f"/blockers/release/{release['id']}", json={
        "title": "Test blocker",
        "severity": "high",
        "assigned_to": "Test Engineer"
    })
    assert response.status_code == 201
    assert response.json()["title"] == "Test blocker"
    assert response.json()["severity"] == "high"
    assert response.json()["status"] == "open"


def test_resolve_blocker():
    """Resolving a blocker changes its status"""
    # Create release + blocker
    release = client.post("/releases/", json={"name": "R", "version": "v1", "owner": "O"}).json()
    blocker = client.post(f"/blockers/release/{release['id']}", json={"title": "Block", "severity": "low"}).json()

    # Resolve it
    response = client.post(f"/blockers/{blocker['id']}/resolve")
    assert response.status_code == 200
    assert response.json()["status"] == "resolved"
    assert response.json()["resolved_at"] is not None


def test_dora_metrics_empty():
    """DORA metrics endpoint works even with no deploy events"""
    response = client.get("/metrics/dora")
    assert response.status_code == 200
    data = response.json()
    # Should return all four metrics
    assert "deploy_frequency" in data
    assert "lead_time_hours" in data
    assert "change_failure_rate" in data
    assert "mttr_minutes" in data
    assert "performance_band" in data


def test_invalid_status_filter():
    """Filtering releases by invalid status returns 400"""
    response = client.get("/releases/?status=invalid_status")
    assert response.status_code == 400
