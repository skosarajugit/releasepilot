# backend/config.py
#
# This file reads all your environment variables from the .env file
# and makes them available throughout the app as `settings.VARIABLE_NAME`.
#
# Why use this instead of os.getenv() everywhere?
#   - Type safety: pydantic validates and converts types automatically
#   - Single source of truth: all config in one place
#   - Easy to see what env vars the app needs

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    # ── Database ─────────────────────────────────────────────
    DATABASE_URL: str = "sqlite:///./releasepilot.db"

    # ── AI (Ollama) ───────────────────────────────────────────
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "tinyllama"

    # ── Slack ─────────────────────────────────────────────────
    # Optional — if blank, notifications just print to console
    SLACK_WEBHOOK_URL: str = ""

    # ── GitHub ────────────────────────────────────────────────
    # Optional — if blank, mock data is used instead
    GITHUB_TOKEN: str = ""
    GITHUB_REPO: str = "skosarajugit/releasepilot"

    # ── App ───────────────────────────────────────────────────
    APP_NAME: str = "ReleasePilot"
    APP_ENV: str = "development"
    BACKEND_URL: str = "http://localhost:8000"

    class Config:
        # Tells pydantic to read from a .env file
        # Copy .env.example to .env and fill in your values
        env_file = ".env"
        env_file_encoding = "utf-8"


# Create a single shared instance — import this everywhere:
#   from backend.config import settings
#   print(settings.DATABASE_URL)
settings = Settings()
