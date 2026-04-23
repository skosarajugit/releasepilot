# ReleasePilot 🚀

An AI-powered Release Manager dashboard built with Python.
Designed as a portfolio project for DevOps/Release Manager roles.

---

## What You'll Learn Building This

- **FastAPI** — building REST APIs in Python
- **SQLAlchemy** — working with databases using Python classes (no raw SQL)
- **Pydantic** — validating data automatically
- **Pandas** — analyzing data and calculating metrics
- **Streamlit** — building interactive dashboards in pure Python
- **Ollama** — running AI models locally for free
- **Docker** — packaging everything into containers

---

## Prerequisites

Install these before starting:

### 1. Python 3.11+
```bash
python --version   # Should be 3.11 or higher
```

### 2. Ollama (free local AI — no API key needed)
```bash
# Mac
brew install ollama

# Linux
curl -fsSL https://ollama.com/install.sh | sh

# Windows — download from https://ollama.com/download
```

Then pull the model (download once, ~4GB):
```bash
ollama pull llama3
ollama serve        # Start the AI server (keep this running)
```

### 3. Docker (for Phase 7)
Download Docker Desktop from https://www.docker.com/products/docker-desktop/

---

## Setup (Phase 1)

```bash
# 1. Clone or create the project folder
cd releasepilot

# 2. Create a virtual environment
# A virtual environment keeps this project's packages separate from other projects
python -m venv venv

# 3. Activate the virtual environment
source venv/bin/activate        # Mac/Linux
venv\Scripts\activate           # Windows

# 4. Install all dependencies
pip install -r requirements.txt

# 5. Copy environment variables file
cp .env.example .env
# Open .env and review the settings (defaults work for local dev)

# 6. Seed the database with demo data
python -m backend.seed_data

# You should see:
# 🌱 Seeding ReleasePilot database...
# ✅ Seeded successfully!
```

---

## Project Structure

```
releasepilot/
├── backend/              ← FastAPI server
│   ├── config.py         ← App settings (reads .env)
│   ├── database.py       ← Database connection setup
│   ├── models.py         ← Database tables (as Python classes)
│   ├── schemas.py        ← API request/response shapes
│   ├── seed_data.py      ← Demo data generator
│   ├── routers/          ← API endpoints (Phase 2)
│   └── services/         ← Business logic (Phase 2-5)
│
├── dashboard/            ← Streamlit UI (Phase 6)
│
├── docker/               ← Docker config (Phase 7)
│
├── tests/                ← Automated tests (Phase 7)
│
├── .env.example          ← Environment variables template
├── requirements.txt      ← Python dependencies
└── README.md             ← This file
```

---

## Phases

| Phase | What you build | Status |
|-------|---------------|--------|
| 1 | Database models + seed data | ✅ Complete |
| 2 | FastAPI REST endpoints | 🔜 Next |
| 3 | Pandas DORA metrics engine | 🔜 |
| 4 | GitHub + Jenkins mock integration | 🔜 |
| 5 | Slack webhook notifications | 🔜 |
| 6 | Streamlit dashboard | 🔜 |
| 7 | Docker + GitHub Actions CI | 🔜 |

---

## Verify Phase 1 Works

After seeding, check the database:
```bash
# Install sqlite3 browser (optional, visual tool)
# Or use the command line:
sqlite3 releasepilot.db

# Inside sqlite3:
.tables                          # List all tables
SELECT name, version, status FROM releases;
SELECT COUNT(*) FROM deploy_events;
.quit
```

You should see 6 releases and hundreds of deploy events.

---

## Key Concepts for Beginners

**What is an ORM?**
Instead of writing `SELECT * FROM releases WHERE id = 1`, you write:
`db.query(Release).filter(Release.id == 1).first()`
SQLAlchemy translates your Python into SQL automatically.

**What is a virtual environment?**
A folder that contains Python + all packages for THIS project only.
Keeps projects isolated so they don't conflict with each other.

**What is Pydantic?**
A library that validates data. If your API expects `{"name": "POS-Core"}` but
someone sends `{"name": 123}`, Pydantic catches it and returns a clear error.

**What is Ollama?**
A tool that runs AI language models (like Llama 3) on your own computer.
Same capability as ChatGPT/Claude, but completely free and private.
