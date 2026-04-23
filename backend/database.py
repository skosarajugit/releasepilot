# backend/database.py
#
# This file sets up the database connection.
# SQLAlchemy is an ORM (Object Relational Mapper) — it lets you
# work with database tables as Python classes instead of writing raw SQL.
#
# How it works:
#   1. engine     → the actual connection to the database file/server
#   2. SessionLocal → a "session" is like a transaction — you open one,
#                     do your reads/writes, then close it
#   3. Base       → all your models (tables) will inherit from this

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, DeclarativeBase
from backend.config import settings

# create_engine() reads the DATABASE_URL from your .env file.
# - For SQLite:     "sqlite:///./releasepilot.db"  → creates a local file
# - For PostgreSQL: "postgresql://user:pass@host/db" → connects to a server
#
# connect_args={"check_same_thread": False} is SQLite-specific.
# SQLite only allows one thread to use a connection by default,
# but FastAPI handles requests in multiple threads, so we disable this check.
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
)

# SessionLocal is a "factory" — every time you call SessionLocal()
# you get a fresh database session (like opening a new transaction).
SessionLocal = sessionmaker(
    autocommit=False,   # Don't auto-save changes — we control when to commit
    autoflush=False,    # Don't auto-send SQL to DB — wait until we ask
    bind=engine         # Use our engine (database connection)
)

# Base is the parent class for all our database models.
# When a class inherits from Base and defines __tablename__,
# SQLAlchemy knows it represents a database table.
class Base(DeclarativeBase):
    pass


def get_db():
    """
    FastAPI dependency that provides a database session per request.

    Usage in a route:
        @router.get("/releases")
        def get_releases(db: Session = Depends(get_db)):
            return db.query(Release).all()

    The 'yield' makes this a generator — FastAPI will:
      1. Call get_db() → open a session
      2. Inject it into your route function
      3. After the route finishes, run the code after 'yield' (close the session)

    This ensures sessions are always closed, even if an error occurs.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Creates all database tables based on the models defined in models.py.
    This is called once at app startup.
    In production you'd use Alembic migrations instead — but this is fine for dev.
    """
    # Import models here so Base knows about them before creating tables
    from backend import models  # noqa: F401 — imported for side effects
    Base.metadata.create_all(bind=engine)
