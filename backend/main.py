from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.database import create_tables
from backend.routers import releases, blockers, pipeline, ai, metrics, notifications

app = FastAPI(
    title="ReleasePilot API",
    description="AI-powered Release Manager backend for Clover POS",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(releases.router,      prefix="/releases",      tags=["Releases"])
app.include_router(blockers.router,      prefix="/blockers",      tags=["Blockers"])
app.include_router(pipeline.router,      prefix="/pipeline",      tags=["Pipeline"])
app.include_router(metrics.router,       prefix="/metrics",       tags=["Metrics"])
app.include_router(ai.router,            prefix="/ai",            tags=["AI"])
app.include_router(notifications.router, prefix="/notifications", tags=["Notifications"])

@app.on_event("startup")
def on_startup():
    create_tables()
    print("✅ ReleasePilot API started")
    print("📖 Docs: http://localhost:8000/docs")

@app.get("/health", tags=["Health"])
def health_check():
    return {"status": "ok", "app": "ReleasePilot"}

@app.get("/", tags=["Health"])
def root():
    return {
        "message": "Welcome to ReleasePilot API",
        "docs": "http://localhost:8000/docs",
        "endpoints": ["/releases", "/blockers", "/pipeline", "/metrics", "/ai", "/notifications"]
    }