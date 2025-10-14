from __future__ import annotations

from contextlib import contextmanager
from typing import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .core.config import get_settings
import os


_settings = get_settings()


def _normalize_db_url(url: str | None) -> str:
    if not url or url.strip() == "":
        # Prefer an existing local SQLite file if present (e.g., serendigo.db), otherwise dev.db
        try:
            if os.path.exists("./serendigo.db"):
                return "sqlite:///./serendigo.db"
        except Exception:
            pass
        return "sqlite:///./dev.db"
    u = url.strip()
    # If async driver is specified, fallback to sync equivalent for this app
    if u.startswith("sqlite+aiosqlite"):
        u = u.replace("sqlite+aiosqlite", "sqlite", 1)
    if "+aiomysql" in u:
        u = u.replace("+aiomysql", "+pymysql", 1)
    return u


_DATABASE_URL = _normalize_db_url(_settings.database_url)

# For SQLite, need check_same_thread=False when used across threads
engine = create_engine(
    _DATABASE_URL,
    connect_args={"check_same_thread": False} if _DATABASE_URL.startswith("sqlite") else {},
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
        # Do not auto-commit here; let handlers control commit timing
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:  # FastAPI Depends
    with session_scope() as db:
        yield db
