"""Database setup and session management."""
import os
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker, Session
from .models import Base

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./medfreedom.db")

# Render provides postgres:// but SQLAlchemy 2.x requires postgresql://
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql://", 1)

# SQLite-specific: enable WAL mode and foreign keys
connect_args = {}
engine_kwargs = {"echo": False}
if DATABASE_URL.startswith("sqlite"):
    connect_args = {"check_same_thread": False}
else:
    # Postgres (Render free tier): keep the pool small and resilient.
    # pool_pre_ping avoids "connection already closed" after the DB sleeps;
    # pool_recycle drops connections older than 5 min so they never go stale.
    engine_kwargs.update(
        pool_size=5,
        max_overflow=5,
        pool_pre_ping=True,
        pool_recycle=300,
        pool_timeout=30,
    )

engine = create_engine(DATABASE_URL, connect_args=connect_args, **engine_kwargs)


@event.listens_for(engine, "connect")
def _set_sqlite_pragma(dbapi_connection, connection_record):
    if DATABASE_URL.startswith("sqlite"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def init_db():
    """Create tables if they do not already exist (non-destructive, idempotent)."""
    Base.metadata.create_all(bind=engine)


def reset_db():
    """Drop and recreate all tables. Destructive — used only for an explicit reseed."""
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)


def get_db():
    """Dependency for FastAPI route handlers."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
