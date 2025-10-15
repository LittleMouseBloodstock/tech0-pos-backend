from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Iterator, Optional

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from .core.config import get_settings


_settings = get_settings()


def _normalize_db_url(url: str | None) -> str:
    if not url or url.strip() == "":
        try:
            if os.path.exists("./serendigo.db"):
                return "sqlite:///./serendigo.db"
        except Exception:
            pass
        return "sqlite:///./dev.db"
    u = url.strip()
    # Ensure sync driver
    if u.startswith("sqlite+aiosqlite"):
        u = u.replace("sqlite+aiosqlite", "sqlite", 1)
    if "+aiomysql" in u:
        u = u.replace("+aiomysql", "+pymysql", 1)
    return u


def _resolve_ssl_connect_args(db_url: str) -> dict:
    if not db_url.startswith("mysql"):
        return {}
    # Prefer explicit env var from app settings or Azure Configuration
    env_path: Optional[str] = os.getenv("SSL_CA_PATH")
    candidates: list[str] = []
    if env_path:
        candidates.append(env_path)
    base_dir = os.path.dirname(os.path.abspath(__file__))
    # Try common filenames (with/without space, G2/RootCA variants)
    candidates.extend(
        [
            os.path.normpath(os.path.join(base_dir, "../DigiCertGlobalRootG2.crt.pem")),
            os.path.normpath(os.path.join(base_dir, "../DigiCertGlobalRootG2.crt .pem")),
            os.path.normpath(os.path.join(base_dir, "../DigiCertGlobalRootCA.crt.pem")),
        ]
    )
    ssl_ca: Optional[str] = None
    for p in candidates:
        try:
            if p and os.path.exists(p):
                ssl_ca = p
                break
        except Exception:
            pass
    if ssl_ca:
        return {"ssl": {"ssl_ca": ssl_ca}}
    # Fallback to system CA store if file not found to avoid startup crash
    return {}


_DATABASE_URL = _normalize_db_url(_settings.database_url)

connect_args: dict = {}
if _DATABASE_URL.startswith("mysql"):
    connect_args = _resolve_ssl_connect_args(_DATABASE_URL)
elif _DATABASE_URL.startswith("sqlite"):
    # Relax thread check for SQLite
    connect_args = {"check_same_thread": False}


engine = create_engine(
    _DATABASE_URL,
    connect_args=connect_args,
    future=True,
)

SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    db = SessionLocal()
    try:
        yield db
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def get_db() -> Iterator[Session]:
    with session_scope() as db:
        yield db

